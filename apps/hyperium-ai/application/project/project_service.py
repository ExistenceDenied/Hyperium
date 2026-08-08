from __future__ import annotations

import logging

from application.analysis.analysis_service import AnalysisService
from application.execution.execution_engine import ExecutionEngine
from application.planning.planning_application_service import (
    PlanningApplicationService,
)
from core.missions.mission import Mission
from core.project.project import Project
from core.resources.resource import Resource

logger = logging.getLogger(__name__)


class ProjectService:
    """
    Orchestrates the complete project lifecycle.

    An engagement is not a single call. `start` analyses, plans and executes
    until it reaches the first approval gate; `resume` continues once a human
    has decided. Both persist the project so the process may exit in between.
    """

    def __init__(
        self,
        analysis_service: AnalysisService,
        planning_service: PlanningApplicationService,
        execution_engine: ExecutionEngine,
        repository=None,
    ) -> None:
        self._analysis_service = analysis_service
        self._planning_service = planning_service
        self._execution_engine = execution_engine
        self._repository = repository

    def start(
        self,
        mission: Mission,
        resources: list[Resource],
    ) -> Project:
        mission.validate()

        project = Project.from_mission(mission)

        logger.info("Analysing mission '%s'.", mission.title)
        project.analysis = self._analysis_service.analyze(mission)

        project.execution_plan = self._planning_service.create_execution_plan(
            project.analysis,
            resources,
            mission=mission,
        )

        return self._run(project)

    def approve(
        self,
        project: Project,
        deliverable_key: str,
        note: str | None = None,
    ) -> Project:
        """
        Record a human's approval of a deliverable.

        Approval lives here, not in an interface. Both the CLI and the web
        review UI perform the same governance act, and 12-interfaces.md states
        the rule: if two interfaces would have to implement it, it belongs in
        the domain. When it lived in the adapters they drifted — only one of
        them required feedback on rejection.
        """
        project.approve(deliverable_key, summary=note)
        logger.info(
            "Deliverable '%s' approved on engagement %s.",
            deliverable_key,
            project.id,
        )
        self._persist(project)

        return project

    def request_changes(
        self,
        project: Project,
        deliverable_key: str,
        note: str,
    ) -> Project:
        """
        Send a deliverable back for rework.

        Feedback is mandatory: it becomes the brief the model reworks against,
        so a rejection without it regenerates the same document blind.
        """
        if not note or not note.strip():
            raise ValueError(
                "Feedback is required when sending a deliverable back - it is "
                "passed to the model as the rework brief."
            )

        project.request_changes(deliverable_key, summary=note.strip())
        logger.info(
            "Deliverable '%s' sent back on engagement %s.",
            deliverable_key,
            project.id,
        )
        self._persist(project)

        return project

    def submit_work(
        self,
        project: Project,
        activity_key: str,
        content: str,
        resume: bool = True,
    ) -> Project:
        """
        Record the output of an activity performed outside Hyperium.

        This is what makes HumanResource a real resource rather than a
        modelling exercise: a person (or a tool operator) does the work, hands
        the result back here, and the engagement carries on.
        """
        if project.execution_plan is None:
            raise ValueError("This project has no plan to submit work against.")

        if not content.strip():
            raise ValueError("Submitted work cannot be empty.")

        plan = project.execution_plan
        activity = plan.activity_by_key(activity_key)

        if activity is None:
            known = ", ".join(item.key for item in plan.activities) or "none"
            raise ValueError(
                f"No activity '{activity_key}' in this engagement. "
                f"Known: {known}."
            )

        if activity.is_completed:
            raise ValueError(
                f"Activity '{activity_key}' has already been completed."
            )

        resource = plan.get_resource(activity)

        if resource is not None and resource.executes_autonomously:
            raise ValueError(
                f"Activity '{activity_key}' is allocated to the autonomous "
                f"resource '{resource.name}' and is executed by Hyperium. "
                f"Reallocate it before submitting work by hand."
            )

        if not plan.is_ready(activity):
            raise ValueError(
                f"Activity '{activity_key}' is not ready: an upstream "
                f"activity is incomplete or its deliverable is unapproved."
            )

        activity.complete(content.strip())

        logger.info(
            "Work submitted for activity '%s' by '%s'.",
            activity_key,
            resource.name if resource else "unallocated",
        )

        if not resume:
            self._persist(project)
            return project

        return self._run(project)

    def resume(self, project: Project) -> Project:
        if project.execution_plan is None:
            raise ValueError(
                "Cannot resume a project that has never been planned."
            )

        logger.info("Resuming engagement %s.", project.id)

        return self._run(project)

    def _run(self, project: Project) -> Project:
        project.execution_result = self._execution_engine.execute(
            project.execution_plan,
            project.mission,
        )

        self._persist(project)

        return project

    def _persist(self, project: Project) -> None:
        if self._repository is None:
            return

        path = self._repository.save(project)
        logger.info("Engagement saved to %s.", path)
