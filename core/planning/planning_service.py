from core.analysis.analysis_result import AnalysisResult
from core.execution.execution_plan import ExecutionPlan


class PlanningService:
    """
    Converts an AnalysisResult into an ExecutionPlan.
    """

    def create_plan(self, analysis: AnalysisResult) -> ExecutionPlan:
        plan = ExecutionPlan()

        for deliverable in analysis.deliverables:
            for activity in deliverable.activities:
                plan.add_activity(activity)

        return plan