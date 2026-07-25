from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionRequest:
    """A side-effecting tool call awaiting a human decision."""

    tool: str
    arguments: dict
    preview: str


@dataclass(frozen=True)
class ApprovalDecision:
    """The verdict on an ActionRequest, with a reason the model can read."""

    approved: bool
    reason: str | None = None

    @classmethod
    def allow(cls, reason: str | None = None) -> "ApprovalDecision":
        return cls(approved=True, reason=reason)

    @classmethod
    def deny(cls, reason: str | None = None) -> "ApprovalDecision":
        return cls(approved=False, reason=reason)
