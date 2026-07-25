from core.execution.deliverable import Deliverable
from core.execution.execution_plan import ExecutionPlan
from core.planning.dependency_graph import topological_order


class PlanningService:
    """
    Turns a set of deliverables into an ordered ExecutionPlan.

    Ordering is Hyperium's responsibility, not the model's: the methodology
    supplies the dependency edges, planning resolves them into a deterministic
    execution order and rejects any graph that cannot be executed.
    """

    def create_plan(self, deliverables: list[Deliverable]) -> ExecutionPlan:
        activities = [
            activity
            for deliverable in deliverables
            for activity in deliverable.activities
        ]

        plan = ExecutionPlan(deliverables=list(deliverables))

        for activity in topological_order(activities):
            plan.add_activity(activity)

        return plan
