from __future__ import annotations

from application.analysis.analysis_service import AnalysisService
from application.execution.activity_executor import (
    ActivityExecutor,
    LlmActivityExecutor,
)
from application.execution.capability_matcher import CapabilityMatcher
from application.execution.execution_engine import ExecutionEngine
from application.execution.resource_allocator import ResourceAllocator
from application.planning.planning_application_service import (
    PlanningApplicationService,
)
from application.project.project_service import ProjectService
from core.analysis.mission_analysis_service import MissionAnalysisService
from core.execution.prompting.activity_prompt_builder import (
    ActivityPromptBuilder,
)
from core.interfaces.artifact_store import ArtifactStore
from core.interfaces.llm_provider import LLMProvider
from core.planning.planning_service import PlanningService


class ProjectBuilder:
    """
    Composes the services required to run an engagement.

    This is the composition root: the only place that knows which concrete
    provider, artifact store, repository and methodology library are in play.
    """

    @staticmethod
    def build(
        llm: LLMProvider,
        artifact_store: ArtifactStore,
        repository=None,
        allocator: ResourceAllocator | None = None,
        methodologies=None,
        default_methodology: str | None = None,
        activity_executor: ActivityExecutor | None = None,
        templates=None,
    ) -> ProjectService:
        catalogue = methodologies.all() if methodologies else []

        # Analysis stays a single completion — it recommends a methodology and
        # nothing more. Only activity content production is pluggable, defaulting
        # to the one-shot LLM so behaviour is unchanged unless a caller opts into
        # an agentic executor.
        executor = activity_executor or LlmActivityExecutor(llm)

        return ProjectService(
            analysis_service=AnalysisService(
                MissionAnalysisService(llm, methodologies=catalogue)
            ),
            planning_service=PlanningApplicationService(
                PlanningService(),
                allocator or ResourceAllocator(CapabilityMatcher()),
                methodologies=methodologies,
                default_methodology=default_methodology,
            ),
            execution_engine=ExecutionEngine(
                executor,
                artifact_store,
                prompt_builder=ActivityPromptBuilder(
                    techniques=methodologies, templates=templates
                ),
            ),
            repository=repository,
        )
