from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionStatus(str, Enum):
    """
    Outcome of an execution pass.

    AWAITING_APPROVAL is a first-class success state, not a failure: the run
    did everything it was permitted to do and is now waiting on a human.
    """

    COMPLETED = "COMPLETED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass
class ExecutionResult:
    """
    Represents the result of executing an execution plan.
    """

    started_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    messages: list[str] = field(default_factory=list)
    activities_executed: int = 0
    deliverables_produced: list[str] = field(default_factory=list)

    @property
    def successful(self) -> bool:
        return self.status in (
            ExecutionStatus.COMPLETED,
            ExecutionStatus.AWAITING_APPROVAL,
        )

    @property
    def is_awaiting_approval(self) -> bool:
        return self.status is ExecutionStatus.AWAITING_APPROVAL

    def add_message(self, message: str) -> None:
        self.messages.append(message)

    def finish(self, status: ExecutionStatus) -> ExecutionResult:
        self.status = status
        self.completed_at = _now()
        return self
