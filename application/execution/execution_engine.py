from datetime import datetime

from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult


class ExecutionEngine:
    """
    Executes an execution plan.

    For now this implementation only validates the plan structure.
    Actual execution of AI, humans and tools will be added later.
    """

    def execute(self, plan: ExecutionPlan) -> ExecutionResult:
        result = ExecutionResult(started_at=datetime.utcnow())

        for activity in plan.activities:
            resource = plan.get_resource(activity)

            if resource is None:
                result.successful = False
                result.add_message(
                    f"No resource assigned to activity '{activity.name}'."
                )
                result.completed_at = datetime.utcnow()
                return result

            result.add_message(
                f"Activity '{activity.name}' assigned to '{resource.name}'."
            )

        result.completed_at = datetime.utcnow()
        return result