from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from core.execution.activity import Activity
from core.resources.resource import Resource


@dataclass
class ExecutionPlan:
    """
    Represents the allocation of resources to activities.
    """

    activities: list[Activity] = field(default_factory=list)
    allocations: dict[UUID, Resource] = field(default_factory=dict)

    def add_activity(self, activity: Activity) -> None:
        if activity not in self.activities:
            self.activities.append(activity)

    def assign(self, activity: Activity, resource: Resource) -> None:
        self.add_activity(activity)
        self.allocations[activity.id] = resource

    def get_resource(self, activity: Activity) -> Resource | None:
        return self.allocations.get(activity.id)