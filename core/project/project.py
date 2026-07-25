from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from core.analysis.analysis_result import AnalysisResult
from core.execution.deliverable import Deliverable
from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult
from core.missions.mission import Mission


class UnknownDeliverableError(KeyError):
    """
    Raised when a review decision names a deliverable the project lacks.
    """


@dataclass
class Project:
    """
    Represents the complete lifecycle of a mission.
    """

    id: UUID
    mission: Mission
    analysis: AnalysisResult | None = None
    execution_plan: ExecutionPlan | None = None
    execution_result: ExecutionResult | None = None

    @classmethod
    def from_mission(cls, mission: Mission) -> "Project":
        return cls(
            id=uuid4(),
            mission=mission,
        )

    @property
    def deliverables(self) -> list[Deliverable]:
        """
        The deliverables belong to the plan, not to the analysis.

        ADR-002: analysis never creates execution plans. Reading them from
        the analysis object made that rule false in the one place it mattered.
        """
        if self.execution_plan is None:
            return []

        return list(self.execution_plan.deliverables)

    @property
    def awaiting_approval(self) -> list[Deliverable]:
        if self.execution_plan is None:
            return []

        return self.execution_plan.awaiting_approval()

    @property
    def is_awaiting_approval(self) -> bool:
        return bool(self.awaiting_approval)

    def deliverable(self, key: str) -> Deliverable:
        for deliverable in self.deliverables:
            if deliverable.key == key:
                return deliverable

        known = ", ".join(item.key for item in self.deliverables) or "none"

        raise UnknownDeliverableError(
            f"No deliverable '{key}' in this project. Known: {known}."
        )

    def approve(self, key: str, summary: str | None = None) -> Deliverable:
        deliverable = self.deliverable(key)
        deliverable.approve(summary)

        return deliverable

    def request_changes(
        self,
        key: str,
        summary: str | None = None,
    ) -> Deliverable:
        deliverable = self.deliverable(key)
        deliverable.request_changes(summary)

        return deliverable
