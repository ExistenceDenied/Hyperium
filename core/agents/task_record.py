from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4

from core.agents.agent_result import AgentResult


def _now() -> datetime:
    return datetime.now(timezone.utc)

PRIORITIES = ("low", "medium", "high")


@dataclass
class Note:
    """A note added to a task — a comment, or a record of what happened."""

    text: str
    at: datetime = field(default_factory=_now)


@dataclass
class Exchange:
    """
    One finished turn in a task's thread: what was asked and what came back.

    A task is a conversation, not a single shot. When someone replies to a
    finished task ("now make it shorter"), the turn that just completed is kept
    here so the next run has the thread behind it and the page can show it.
    """

    prompt: str
    output: str
    at: datetime = field(default_factory=_now)


@dataclass
class TaskRecord:
    """
    A durable record of one direct-task run — a ticket, in effect: what was
    asked, at what priority, what happened, when, and the notes people added.

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
    #: Absolute paths of the files this task produced, so a person can find and
    #: open the deliverable without hunting for it.
    artifacts: list[str] = field(default_factory=list)
    priority: str = "medium"
    completed_at: datetime | None = None
    notes: list[Note] = field(default_factory=list)
    #: An optional technique or methodology whose approach the task should
    #: follow — its guidance and template shape how the agent works.
    technique: str = ""
    methodology: str = ""
    #: True while the task is in the queue, waiting for the worker to launch it.
    queued: bool = False
    #: Earlier turns of this task's thread. The current turn is `prompt` and
    #: `result`; each reply pushes the previous turn here.
    history: list[Exchange] = field(default_factory=list)

    @property
    def status(self) -> str:
        """queued → running elsewhere; its outcome once it has one."""
        if self.result is not None:
            return self.result.stop_reason.value

        return "queued" if self.queued else "pending"

    @property
    def acted(self) -> bool:
        """Whether the run performed any tool call at all."""
        return bool(self.result and self.result.steps)

    @property
    def duration_seconds(self) -> float | None:
        """How long the task took, once it has finished."""
        if self.completed_at is None:
            return None

        return (self.completed_at - self.created_at).total_seconds()
