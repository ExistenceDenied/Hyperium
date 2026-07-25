from core.analysis.analysis_result import AnalysisResult
from core.execution.execution_plan import ExecutionPlan
from core.planning.dependency_graph import topological_order


class PlanningService:
    """
    Converts an AnalysisResult into an ExecutionPlan.

    Ordering is Hyperium's responsibility, not the model's: the analysis
    supplies the dependency edges, planning resolves them into a deterministic
    execution order and rejects any graph that cannot be executed.
    """

    def create_plan(self, analysis: AnalysisResult) -> ExecutionPlan:
        activities = [
            activity
            for deliverable in analysis.deliverables
            for activity in deliverable.activities
        ]

        plan = ExecutionPlan(deliverables=list(analysis.deliverables))

        for activity in topological_order(activities):
            plan.add_activity(activity)

        return plan
