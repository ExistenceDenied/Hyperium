from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from core.agents.agent_result import AgentResult


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TaskRecord:
    """
    A durable record of one direct-task run: what was asked, and what happened.

    This is the audit trail and memory of the direct-task path. A record is
    written for every run, so the question 'what has the agent done, and did it
    act?' has an answer that outlives the process — the same standard the
    engagement side already holds itself to.
    """

    prompt: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
    model: str | None = None
    result: AgentResult | None = None

    @property
    def status(self) -> str:
        """Derived from the run's outcome; 'pending' until it has one."""
        if self.result is None:
            return "pending"

        return self.result.stop_reason.value

    @property
    def acted(self) -> bool:
        """Whether the run performed any tool call at all."""
        return bool(self.result and self.result.steps)
