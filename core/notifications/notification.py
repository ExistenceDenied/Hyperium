from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID, uuid4


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Notification:
    """
    Something that happened that a person may want to know about.

    The system now acts on its own — tasks finish, and some pause to ask
    permission — so there has to be a place those moments surface rather than
    being missed. A notification is one such moment, with a link to act on it.
    """

    text: str
    id: UUID = field(default_factory=uuid4)
    kind: str = "task"  # task | approval | error
    link: str = ""
    read: bool = False
    at: datetime = field(default_factory=_now)
