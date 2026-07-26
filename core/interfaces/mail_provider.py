from __future__ import annotations

from abc import ABC, abstractmethod

from core.email.email_message import EmailMessage


class MailProvider(ABC):
    """
    A mailbox the system can read and draft into — but never send from.

    Draft-only is enforced here, in the type: there is no `send`. The worker
    physically cannot send a reply, because nothing in the interface can. A reply
    it writes becomes a draft in your mailbox that you review and send yourself.
    """

    @abstractmethod
    def list_messages(self, folder: str) -> list[EmailMessage]:
        """Return the messages currently in the given folder."""
        raise NotImplementedError

    @abstractmethod
    def create_draft_reply(self, message: EmailMessage, body: str) -> None:
        """Save a reply to `message` as a draft. It is never sent."""
        raise NotImplementedError
