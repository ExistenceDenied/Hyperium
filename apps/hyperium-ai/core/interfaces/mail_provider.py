from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from core.email.email_message import EmailMessage

# A file to attach: its name and raw bytes.
Attachment = tuple[str, bytes]


class MailProvider(ABC):
    """
    A mailbox the system can read and reply to.

    Replies are always threaded to the original message, so a reply can only ever
    go back to the sender — never a recipient a rule invents. Sending is a real,
    irreversible action, kept separate from drafting: the worker only calls
    `send_reply` when a business rule says to and the outbound switch is on;
    otherwise it drafts, and a person sends.
    """

    @abstractmethod
    def list_messages(self, folder: str, since=None) -> list[EmailMessage]:
        """Return messages in the folder, optionally only those newer than `since`."""
        raise NotImplementedError

    @abstractmethod
    def draft_reply(
        self, message: EmailMessage, body: str, attachments: Sequence[Attachment] = ()
    ) -> None:
        """Save a threaded reply as a draft. Never sent."""
        raise NotImplementedError

    @abstractmethod
    def send_reply(
        self, message: EmailMessage, body: str, attachments: Sequence[Attachment] = ()
    ) -> None:
        """Send a threaded reply to the original sender. Irreversible."""
        raise NotImplementedError
