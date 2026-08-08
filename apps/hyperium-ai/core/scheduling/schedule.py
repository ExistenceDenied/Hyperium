from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


CADENCES = {"hourly": 1, "daily": 24, "weekly": 168}


@dataclass
class Schedule:
    """
    A task set to run on a cadence.

    This is what makes the system run on a clock: when a schedule is due, its
    task is added to the queue and the worker runs it — "every Monday draft the
    newsletter" becomes real. It reuses everything: memory, techniques and
    methodologies all apply to the task it queues.
    """

    prompt: str
    id: UUID = field(default_factory=uuid4)
    every_hours: int = 24
    priority: str = "medium"
    technique: str = ""
    methodology: str = ""
    enabled: bool = True
    last_run: datetime | None = None
    created_at: datetime = field(default_factory=_now)

    def is_due(self, now: datetime) -> bool:
        if not self.enabled:
            return False
        if self.last_run is None:
            return True
        return (now - self.last_run).total_seconds() >= self.every_hours * 3600

    @property
    def cadence(self) -> str:
        for name, hours in CADENCES.items():
            if hours == self.every_hours:
                return name
        return f"every {self.every_hours}h"
