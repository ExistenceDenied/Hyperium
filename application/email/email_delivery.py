from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from core.email.email_message import EmailMessage
from core.rules.rule import RuleSet

logger = logging.getLogger(__name__)


class EmailDelivery:
    """
    Feed a finished deliverable back to the email that asked for it.

    When a task spawned by an email produces a file, this replies to that email
    with the file attached — closing the loop from "we're preparing it" to the
    actual thing. It obeys the same rules and outbound switch as any reply:
    draft by default, send only when a rule allows and the switch is on, and
    always threaded back to the original sender only.
    """

    def __init__(
        self,
        provider,
        rules: Callable[[], RuleSet] = lambda: RuleSet([]),
        can_send: Callable[[], bool] = lambda: False,
        notify: Callable[..., object] = lambda kind, text, link="": None,
    ) -> None:
        self._provider = provider
        self._rules = rules
        self._can_send = can_send
        self._notify = notify

    def deliver(self, origin: dict, folder) -> bool:
        if not origin or origin.get("type") != "email":
            return False

        directory = Path(folder)
        files = [
            (path.name, path.read_bytes())
            for path in sorted(directory.iterdir())
            if path.is_file()
        ] if directory.is_dir() else []
        if not files:
            return False  # nothing produced — nothing to deliver

        message = EmailMessage(
            id=str(origin.get("message_id", "")),
            sender=str(origin.get("sender", "")),
            subject=str(origin.get("subject", "")),
            body="",
        )
        names = ", ".join(name for name, _ in files)
        body = (
            "Hi,\n\nAs requested, please find attached: "
            f"{names}.\n\nLet me know if you'd like any changes.\n\nBest regards"
        )

        ruled = self._rules().decide(
            {"sender": message.sender, "subject": message.subject, "category": "reply"}
        )
        want_send = ruled.get("delivery", "draft").strip().lower() == "send"

        if want_send and self._can_send():
            self._provider.send_reply(message, body, files)
            self._notify(
                "email", f"Sent the deliverable ({names}) to {message.sender}", "/tasks"
            )
            return True

        self._provider.draft_reply(message, body, files)
        self._notify(
            "email",
            f"Deliverable draft ready ({names}) for {message.sender}",
            "/email",
        )
        return True
