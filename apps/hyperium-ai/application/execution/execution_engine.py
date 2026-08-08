from __future__ import annotations

import logging

from application.execution.activity_executor import ActivityExecutor
from core.execution.activity import Activity
from core.execution.deliverable import Deliverable
from core.execution.deliverable_status import DeliverableStatus
from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult, ExecutionStatus
from core.execution.prompting.activity_prompt_builder import ActivityPromptBuilder
from core.interfaces.artifact_store import ArtifactStore
from core.missions.mission import Mission
from core.resources.resource import Resource

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    Executes an execution plan, producing real deliverable content.

    The engine runs every activity whose dependencies are satisfied, assembles
    each finished deliverable into a new version, then stops at the approval
    gate. It is re-entrant: calling execute again after a human approves
    resumes exactly where the previous pass left off.
    """

    def __init__(
        self,
        executor: ActivityExecutor,
        artifact_store: ArtifactStore,
        prompt_builder: ActivityPromptBuilder | None = None,
    ) -> None:
        self._executor = executor
        self._artifacts = artifact_store
        self._prompts = prompt_builder or ActivityPromptBuilder()

    def execute(self, plan: ExecutionPlan, mission: Mission) -> ExecutionResult:
        result = ExecutionResult()

        while True:
            # Collected at the top of every pass, not after executing, so
            # that activities completed outside this engine — work submitted
            # by a human — still produce a deliverable version.
            self._collect_finished_deliverables(plan, result)

            ready = [
                activity
                for activity in plan.ready_activities()
                if self._is_executable(plan, activity)
            ]

            if not ready:
                break

            for activity in ready:
                if not self._run(activity, plan, mission, result):
                    return result.finish(ExecutionStatus.FAILED)

        return result.finish(self._final_status(plan, result))

    def _is_executable(self, plan: ExecutionPlan, activity: Activity) -> bool:
        """
        Only autonomous resources execute here. Human and tool resources are
        modelled and allocated, but their work is submitted from outside.
        """
        resource = plan.get_resource(activity)

        return resource is not None and resource.executes_autonomously

    def _run(
        self,
        activity: Activity,
        plan: ExecutionPlan,
        mission: Mission,
        result: ExecutionResult,
    ) -> bool:
        resource = plan.get_resource(activity)
        deliverable = plan.deliverable_for(activity)

        if deliverable is None:
            result.add_message(
                f"Activity '{activity.key}' belongs to no deliverable."
            )
            return False

        prompt = self._prompts.build(
            activity,
            deliverable,
            mission,
            upstream=self._upstream(plan, activity),
            revision_of=(
                deliverable.latest_version()
                if deliverable.status is DeliverableStatus.CHANGES_REQUESTED
                else None
            ),
        )

        logger.info(
            "Executing activity '%s' via '%s'.",
            activity.key,
            resource.name,
        )

        try:
            content = self._executor.execute(prompt, activity)
        except Exception as error:
            activity.fail()
            logger.error("Activity '%s' failed: %s", activity.key, error)
            result.add_message(f"Activity '{activity.key}' failed: {error}")
            return False

        activity.complete(content.strip())
        result.activities_executed += 1
        result.add_message(
            f"Activity '{activity.key}' completed by '{resource.name}'."
        )

        return True

    def _upstream(self, plan: ExecutionPlan, activity: Activity) -> list[Activity]:
        upstream = [
            plan.activity_by_key(key) for key in sorted(activity.depends_on)
        ]

        return [item for item in upstream if item is not None]

    def _collect_finished_deliverables(
        self,
        plan: ExecutionPlan,
        result: ExecutionResult,
    ) -> None:
        for deliverable in plan.deliverables:
            if not deliverable.is_complete:
                continue

            if deliverable.status not in (
                DeliverableStatus.DRAFT,
                DeliverableStatus.CHANGES_REQUESTED,
            ):
                continue

            superseded = deliverable.latest_version()

            version = deliverable.add_version(
                content=self._assemble(deliverable),
                created_by=self._author(plan, deliverable),
            )

            location = self._artifacts.save(version.filename, version.content)
            deliverable.submit_for_approval()

            result.deliverables_produced.append(version.filename)
            result.add_message(
                f"Deliverable '{deliverable.key}' v{version.version} "
                f"written to {location} and is awaiting approval."
            )
            logger.info(
                "Deliverable '%s' v%s awaiting approval.",
                deliverable.key,
                version.version,
            )

            if superseded is not None:
                self._warn_about_stale_downstream(plan, deliverable, result)

    def _warn_about_stale_downstream(
        self,
        plan: ExecutionPlan,
        revised: Deliverable,
        result: ExecutionResult,
    ) -> None:
        """
        A revised deliverable may invalidate work built on the old version.

        Downstream deliverables are not reset automatically — that would
        discard content a human has already approved. They are reported
        instead, so the decision to redo them stays with the reviewer.
        """
        upstream_keys = {activity.key for activity in revised.activities}

        for deliverable in plan.deliverables:
            if deliverable is revised or not deliverable.versions:
                continue

            depends = any(
                upstream_keys & activity.depends_on
                for activity in deliverable.activities
            )

            if depends:
                result.add_message(
                    f"Deliverable '{deliverable.key}' was built on the "
                    f"superseded version of '{revised.key}' and may need to "
                    f"be revised."
                )

    def _assemble(self, deliverable: Deliverable) -> str:
        sections = [f"# {deliverable.name}", ""]

        if deliverable.description:
            sections.extend([deliverable.description, ""])

        for activity in deliverable.activities:
            if activity.output:
                sections.append(activity.output)
                sections.append("")

        return "\n".join(sections).strip() + "\n"

    def _author(self, plan: ExecutionPlan, deliverable: Deliverable) -> str:
        names = {resource.name for resource in self._resources(plan, deliverable)}

        return ", ".join(sorted(names))

    def _resources(
        self,
        plan: ExecutionPlan,
        deliverable: Deliverable,
    ) -> list[Resource]:
        resources = [
            plan.get_resource(activity) for activity in deliverable.activities
        ]

        return [resource for resource in resources if resource is not None]

    def _final_status(
        self,
        plan: ExecutionPlan,
        result: ExecutionResult,
    ) -> ExecutionStatus:
        # Reported before any early return: knowing which stage is gated, and
        # why, is the most useful thing a stalled engagement can tell you.
        for stage_key, gate in plan.open_gates():
            for failure in gate.failures:
                result.add_message(f"Quality gate '{stage_key}': {failure}")

        if plan.awaiting_approval():
            return ExecutionStatus.AWAITING_APPROVAL

        pending = plan.pending_activities()

        if not pending:
            return ExecutionStatus.COMPLETED

        for activity in pending:
            resource = plan.get_resource(activity)

            if resource is None:
                result.add_message(
                    f"No resource has the capabilities for activity "
                    f"'{activity.key}'."
                )
            elif not resource.executes_autonomously:
                result.add_message(
                    f"Activity '{activity.key}' is allocated to "
                    f"'{resource.name}' and awaits work outside Hyperium."
                )
            else:
                result.add_message(
                    f"Activity '{activity.key}' is blocked by an unapproved "
                    f"or incomplete dependency."
                )

        return ExecutionStatus.BLOCKED
