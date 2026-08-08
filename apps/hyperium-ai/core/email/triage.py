from __future__ import annotations

from dataclasses import dataclass, field

# What the agent should do with an email. The primary action per message.
CATEGORIES = ("reply", "escalate", "fyi", "skip")


@dataclass
class TriageDecision:
    """
    The outcome of triaging one email: what it is, and what to do about it.

    Triage before drafting is the whole point — most mail needs no reply, so the
    agent decides an action per message (draft, flag, note, ignore) and only
    spends effort where it pays off. `tasks` is separate from the reply: things
    Hyperium should actually do as a result of the mail, queued for the worker.
    """

    category: str = "fyi"
    priority: str = "medium"
    confidence: float = 0.0
    summary: str = ""
    reason: str = ""
    #: Concrete jobs the mail implies the business should carry out.
    tasks: list[str] = field(default_factory=list)

    @property
    def should_draft(self) -> bool:
        return self.category == "reply"

    @property
    def needs_attention(self) -> bool:
        return self.category == "escalate"
