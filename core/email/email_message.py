from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EmailMessage:
    """
    One received email, as the system reads it.

    A plain value: enough to understand the message and draft a reply, with the
    id the mail service uses so a draft can be attached to the right thread.
    """

    id: str
    sender: str
    subject: str
    body: str
    received_at: datetime | None = None

    @property
    def reply_subject(self) -> str:
        subject = self.subject or "(no subject)"
        return subject if subject.lower().startswith("re:") else f"Re: {subject}"
