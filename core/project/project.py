from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from core.analysis.analysis_result import AnalysisResult
from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult
from core.missions.mission import Mission


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