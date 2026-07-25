from application.analysis.analysis_service import AnalysisService
from application.execution.capability_matcher import CapabilityMatcher
from application.execution.execution_engine import ExecutionEngine
from application.execution.resource_allocator import ResourceAllocator
from application.planning.planning_application_service import (
    PlanningApplicationService,
)
from core.analysis.mission_analysis_service import MissionAnalysisService
from core.interfaces.llm_provider import LLMProvider
from core.planning.planning_service import PlanningService


class ProjectBuilder:
    """
    Composes the application services required to execute a project.
    """

    @staticmethod
    def build(llm: LLMProvider):
        analysis_service = AnalysisService(
            MissionAnalysisService(llm)
        )

        planning_service = PlanningApplicationService(
            PlanningService(),
            ResourceAllocator(
                CapabilityMatcher(),
            ),
        )

        execution_engine = ExecutionEngine()

        return (
            analysis_service,
            planning_service,
            execution_engine,
        )