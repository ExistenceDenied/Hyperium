from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from core.email.email_message import EmailMessage
from core.interfaces.mail_provider import MailProvider

logger = logging.getLogger(__name__)


class Ms365MailProvider(MailProvider):
    """
    Reads Outlook / Microsoft 365 mail and drafts replies, over MCP.

    A thin bridge from the MailProvider port to a Microsoft 365 MCP server's
    tools: it lists a folder's messages and saves a reply as a draft. It never
    sends — the port offers no way to, and this adapter calls no send tool.

    The tool names and field shapes below match a typical Graph-backed MS365 MCP
    server; if yours differs, they are all in one place to adjust. Because it
    depends on your live Outlook sign-in, exercise it against your own mailbox —
    the engine around it is verified with a simulated provider.
    """

    LIST_TOOL = "list-mail-folder-messages"
    DRAFT_TOOL = "create-draft-email"

    def __init__(self, call_tool, limit: int = 25) -> None:
        # call_tool(name, arguments) -> str, e.g. an McpClient's call_tool.
        self._call = call_tool
        self._limit = limit

    def list_messages(self, folder: str) -> list[EmailMessage]:
        raw = self._call(
            self.LIST_TOOL,
            {"mailFolder": folder, "top": self._limit},
        )
        return [self._to_message(item) for item in self._rows(raw)]

    def create_draft_reply(self, message: EmailMessage, body: str) -> None:
        self._call(
            self.DRAFT_TOOL,
            {
                "subject": message.reply_subject,
                "to": [message.sender],
                "body": body,
            },
        )

    # --------------------------------------------------------- internals

    def _rows(self, raw: str) -> list[dict]:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            logger.warning("Could not parse the mail listing as JSON.")
            return []
        if isinstance(data, dict):
            data = data.get("value") or data.get("messages") or data.get("items") or []
        return [row for row in data if isinstance(row, dict)]

    def _to_message(self, row: dict[str, Any]) -> EmailMessage:
        sender = row.get("from") or row.get("sender") or row.get("fromAddress") or ""
        if isinstance(sender, dict):  # Graph nests {emailAddress: {address}}
            sender = (
                sender.get("emailAddress", {}).get("address")
                or sender.get("address")
                or ""
            )
        body = row.get("body")
        if isinstance(body, dict):
            body = body.get("content", "")
        received = row.get("receivedDateTime") or row.get("received_at")
        when = None
        if received:
            try:
                when = datetime.fromisoformat(str(received).replace("Z", "+00:00"))
            except ValueError:
                when = None
        return EmailMessage(
            id=str(row.get("id") or row.get("messageId") or ""),
            sender=str(sender),
            subject=str(row.get("subject") or ""),
            body=str(body or row.get("bodyPreview") or ""),
            received_at=when,
        )
