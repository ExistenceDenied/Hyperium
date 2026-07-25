from __future__ import annotations

import logging

from application.execution.resource_allocator import ResourceAllocator
from core.analysis.analysis_result import AnalysisResult
from core.execution.execution_plan import ExecutionPlan
from core.methodologies.methodology import Methodology
from core.missions.mission import Mission
from core.planning.methodology_planner import MethodologyPlanner
from core.planning.planning_service import PlanningService
from core.resources.resource import Resource

logger = logging.getLogger(__name__)


class PlanningError(RuntimeError):
    """
    Raised when an engagement cannot be planned.
    """


class PlanningApplicationService:
    """
    Orchestrates planning and resource allocation.

    Selecting the methodology is a planning decision: the mission may name one
    explicitly, the analysis may recommend one, and otherwise the configured
    default applies. Once chosen, the methodology determines the work.
    """

    def __init__(
        self,
        planning_service: PlanningService,
        resource_allocator: ResourceAllocator,
        methodologies=None,
        default_methodology: str | None = None,
    ) -> None:
        self._planning_service = planning_service
        self._resource_allocator = resource_allocator
        self._methodologies = methodologies
        self._default = default_methodology
        self._planner = MethodologyPlanner()

    def create_execution_plan(
        self,
        analysis: AnalysisResult,
        resources: list[Resource],
        mission: Mission | None = None,
    ) -> ExecutionPlan:
        if mission is None:
            raise PlanningError(
                "An engagement cannot be planned without a mission."
            )

        methodology = self._select(analysis, mission)

        if methodology is None:
            raise PlanningError(
                "No methodology could be selected for this engagement. "
                "Name one on the mission, configure a default, or let the "
                "analysis recommend one. Hyperium automates methodologies; "
                "it does not invent them."
            )

        # The plan owns the work. It is not written back into the analysis:
        # ADR-002 says analysis never creates execution plans, and routing it
        # through the analysis object made that literally false.
        deliverables = self._planner.build(methodology, mission)

        plan = self._planning_service.create_plan(deliverables)
        plan.stages = self._planner.stages(methodology)
        plan.methodology_key = methodology.key

        for activity in plan.activities:
            resource = self._resource_allocator.allocate(activity, resources)

            if resource is not None:
                plan.assign(activity, resource)

        if not plan.activities:
            raise PlanningError(
                f"Methodology '{methodology.key}' produced no activities. "
                f"An engagement with nothing to do is a planning failure, "
                f"not a completed engagement."
            )

        return plan

    def _select(
        self,
        analysis: AnalysisResult,
        mission: Mission | None,
    ) -> Methodology | None:
        if self._methodologies is None:
            return None

        chosen = None
        source = ""

        if mission is not None and getattr(mission, "methodology", None):
            chosen, source = mission.methodology, "the mission"
        elif analysis.recommended_methodology:
            chosen, source = analysis.recommended_methodology, "the analysis"
        elif self._default:
            chosen, source = self._default, "the default"

        if not chosen:
            return None

        methodology = self._methodologies.get(chosen)

        logger.info("Methodology '%s' selected by %s.", methodology.key, source)

        return methodology
