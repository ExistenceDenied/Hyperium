from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from core.interfaces.mail_provider import MailProvider

logger = logging.getLogger(__name__)


class InboxWorker:
    """
    Reads a mail folder on a clock and drafts a reply to anything new.

    It works like a colleague who watches one folder: for each message it has
    not handled, it writes a reply and leaves it as a draft for you to review and
    send. It never sends — the provider cannot — and it only touches the folder
    you point it at. Handled messages are remembered so a reply is drafted once.
    """

    def __init__(
        self,
        provider: MailProvider,
        responder,
        store,
        context: Callable[[], str] = lambda: "",
        notify: Callable[..., object] = lambda kind, text, link="": None,
    ) -> None:
        self._provider = provider
        self._responder = responder
        self._store = store
        self._context = context
        self._notify = notify

    def tick(self) -> int:
        if not self._store.enabled:
            return 0

        folder = self._store.folder
        try:
            messages = self._provider.list_messages(folder)
        except Exception:
            logger.exception("Could not read the '%s' folder.", folder)
            return 0

        drafted = 0
        for message in messages:
            if self._store.is_handled(message.id):
                continue
            try:
                body = self._responder.compose(message, self._context())
                self._provider.create_draft_reply(message, body)
            except Exception:
                logger.exception("Failed to draft a reply to %s.", message.id)
                continue

            self._store.mark_handled(message.id, message.sender, message.subject)
            self._notify(
                "email",
                f"Draft ready: {message.reply_subject} (to {message.sender})",
                "/email",
            )
            drafted += 1

        return drafted

    def start(self, interval: float = 120.0) -> None:
        def loop() -> None:
            while True:
                try:
                    self.tick()
                except Exception:
                    logger.exception("Inbox worker tick failed.")
                time.sleep(interval)

        threading.Thread(target=loop, daemon=True).start()
