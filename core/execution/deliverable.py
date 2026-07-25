from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.execution.activity import Activity


@dataclass
class Deliverable:
    """
    Represents a business deliverable consisting of one or more activities.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str | None = None
    activities: list[Activity] = field(default_factory=list)

    def add_activity(self, activity: Activity) -> None:
        if activity not in self.activities:
            self.activities.append(activity)