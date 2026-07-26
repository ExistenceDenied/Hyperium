from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


# The kinds of thing worth remembering about a business. Free text is allowed;
# these are the suggested buckets the UI offers.
CATEGORIES = (
    "about",
    "services",
    "pricing",
    "voice",
    "customers",
    "preferences",
    "general",
)


@dataclass
class MemoryEntry:
    """
    One durable fact about the business the agents should know and honour.

    This is the organisation's memory: what it does, what it charges, how it
    sounds, who its customers are, what it prefers. It is read into an agent's
    context so its work is on-brand and consistent, and it outlives any single
    task — the thing that turns a clever tool into *your* business's assistant.
    """

    text: str
    category: str = "general"
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=_now)
