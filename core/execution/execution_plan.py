from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from core.execution.activity import Activity
from core.execution.deliverable import Deliverable
from core.execution.deliverable_status import DeliverableStatus
from core.methodologies.methodology import Methodology
from core.methodologies.quality_gate import GateResult
from core.resources.resource import Resource


@dataclass
class ExecutionPlan:
    """
    The ordered work, the deliverables it produces, and who is allocated to it.

    `activities` is held in dependency order. The plan is also the authority on
    what may run next, because readiness depends on both activity completion
    and the human approval gate on upstream deliverables.
    """

    activities: list[Activity] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)
    allocations: dict[UUID, Resource] = field(default_factory=dict)
    methodology: Methodology | None = None

    def add_activity(self, activity: Activity) -> None:
        if activity not in self.activities:
            self.activities.append(activity)

    def assign(self, activity: Activity, resource: Resource) -> None:
        self.add_activity(activity)
        self.allocations[activity.id] = resource

    def get_resource(self, activity: Activity) -> Resource | None:
        return self.allocations.get(activity.id)

    def deliverable_for(self, activity: Activity) -> Deliverable | None:
        for deliverable in self.deliverables:
            if activity in deliverable.activities:
                return deliverable

        return None

    def activity_by_key(self, key: str) -> Activity | None:
        for activity in self.activities:
            if activity.key == key:
                return activity

        return None

    def deliverables_in_stage(self, stage_key: str) -> list[Deliverable]:
        return [
            deliverable
            for deliverable in self.deliverables
            if deliverable.stage == stage_key
        ]

    def gate_result(self, stage_key: str) -> GateResult:
        """
        Evaluate a stage's quality gate against what it actually produced.

        A stage with no methodology or no gate passes trivially — an
        engagement planned without a methodology behaves exactly as it did
        before 2.0.
        """
        if self.methodology is None:
            return GateResult(True)

        try:
            stage = self.methodology.stage(stage_key)
        except KeyError:
            return GateResult(True)

        if stage.quality_gate is None:
            return GateResult(True)

        return stage.quality_gate.evaluate(self.deliverables_in_stage(stage_key))

    def open_gates(self) -> list[tuple[str, GateResult]]:
        """Stages whose work is finished but whose gate has not yet passed."""
        if self.methodology is None:
            return []

        blocked = []

        for stage in self.methodology.stages:
            deliverables = self.deliverables_in_stage(stage.key)

            if not deliverables:
                continue

            if not all(item.is_complete for item in deliverables):
                continue

            result = self.gate_result(stage.key)

            if not result.passed:
                blocked.append((stage.key, result))

        return blocked

    def _stage_is_open(self, stage_key: str | None) -> bool:
        """Whether work in a stage may begin, based on its upstream gates."""
        if self.methodology is None or stage_key is None:
            return True

        try:
            stage = self.methodology.stage(stage_key)
        except KeyError:
            return True

        return all(
            self.gate_result(upstream).passed for upstream in stage.depends_on
        )

    def is_ready(self, activity: Activity) -> bool:
        """
        An activity is ready when every dependency has completed and, for
        dependencies in *other* deliverables, that deliverable has cleared its
        approval gate.

        The approval condition is what makes human oversight real: downstream
        work cannot consume a document nobody has signed off. It deliberately
        stops at the deliverable boundary — activities within one deliverable
        build the same document, and that document cannot be approved until
        they have all finished. Gating them on their own deliverable's
        approval would deadlock.
        """
        owner = self.deliverable_for(activity)

        # A stage's quality gate governs everything in the next stage, not
        # only the activities with an explicit edge across the boundary.
        if owner is not None and not self._stage_is_open(owner.stage):
            return False

        for key in activity.depends_on:
            dependency = self.activity_by_key(key)

            if dependency is None or not dependency.is_completed:
                return False

            upstream = self.deliverable_for(dependency)

            if upstream is None or upstream is owner:
                continue

            # Deliverables in the same stage are drafted together and
            # reviewed together at that stage's gate. Requiring approval
            # between them would strand a stage half-finished: its own gate
            # cannot pass until every deliverable in it is complete.
            if (
                owner is not None
                and owner.stage is not None
                and owner.stage == upstream.stage
            ):
                continue

            if not upstream.is_approved:
                return False

        return True

    def pending_activities(self) -> list[Activity]:
        return [
            activity
            for activity in self.activities
            if not activity.is_completed
        ]

    def ready_activities(self) -> list[Activity]:
        return [
            activity
            for activity in self.pending_activities()
            if self.is_ready(activity)
        ]

    def awaiting_approval(self) -> list[Deliverable]:
        return [
            deliverable
            for deliverable in self.deliverables
            if deliverable.status is DeliverableStatus.AWAITING_APPROVAL
        ]
