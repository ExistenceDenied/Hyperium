from application.execution.resource_allocator import ResourceAllocator
from core.analysis.analysis_result import AnalysisResult
from core.execution.execution_plan import ExecutionPlan
from core.planning.planning_service import PlanningService
from core.resources.resource import Resource


class PlanningApplicationService:
    """
    Orchestrates planning and resource allocation.
    """

    def __init__(
        self,
        planning_service: PlanningService,
        resource_allocator: ResourceAllocator,
    ) -> None:
        self._planning_service = planning_service
        self._resource_allocator = resource_allocator

    def create_execution_plan(
        self,
        analysis: AnalysisResult,
        resources: list[Resource],
    ) -> ExecutionPlan:
        plan = self._planning_service.create_plan(analysis)

        for activity in plan.activities:
            resource = self._resource_allocator.allocate(activity, resources)

            if resource is not None:
                plan.assign(activity, resource)

        return plan