from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ExecutionResult:
    """
    Represents the result of executing an execution plan.
    """

    started_at: datetime
    completed_at: datetime | None = None
    successful: bool = True
    messages: list[str] = field(default_factory=list)

    def add_message(self, message: str) -> None:
        self.messages.append(message)