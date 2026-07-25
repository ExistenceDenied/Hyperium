from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DeliverableVersion:
    """
    An immutable snapshot of a deliverable's content.

    Each version owns a distinct filename so that revising a deliverable never
    destroys the version that was reviewed.
    """

    version: int
    content: str
    filename: str
    created_by: str = ""
    created_at: datetime = field(default_factory=_now)
    review_summary: str | None = None
