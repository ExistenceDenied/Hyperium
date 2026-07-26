from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from core.interfaces.mail_provider import MailProvider

logger = logging.getLogger(__name__)


class InboxWorker:
    """
    Triages a mail folder on a clock and acts per message, efficiently.

    It works like a colleague who watches one folder. For each new message it
    decides an action rather than replying to everything: draft a reply only
    when one is genuinely needed, flag anything that needs the owner, note the
    merely-informational, and ignore noise. Separately, it turns work the mail
    implies into queued tasks — so the system stays effective, not just
    responsive. It never sends: replies are left as drafts to review.
    """

    def __init__(
        self,
        provider: MailProvider,
        triage,
        responder,
        store,
        enqueue: Callable[..., object] = lambda prompt, **kw: None,
        context: Callable[[], str] = lambda: "",
        notify: Callable[..., object] = lambda kind, text, link="": None,
    ) -> None:
        self._provider = provider
        self._triage = triage
        self._responder = responder
        self._store = store
        self._enqueue = enqueue
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

        handled = 0
        for message in messages:
            if self._store.is_handled(message.id):
                continue
            try:
                self._handle(message)
            except Exception:
                logger.exception("Failed to handle %s.", message.id)
                continue
            handled += 1

        return handled

    def _handle(self, message) -> None:
        context = self._context()
        decision = self._triage.classify(message, context)
        actions: list[str] = []

        if decision.should_draft:
            body = self._responder.compose(message, context)
            self._provider.create_draft_reply(message, body)
            actions.append("drafted a reply")
            self._notify(
                "email",
                f"Draft ready: {message.reply_subject} (to {message.sender})",
                "/email",
            )
        elif decision.needs_attention:
            actions.append("flagged for you")
            self._notify(
                "email",
                f"Needs you: {message.subject} — {decision.summary}",
                "/email",
            )

        # Work the mail implies — queued for the worker regardless of category,
        # so a request buried in an FYI still becomes a task.
        for task in decision.tasks:
            self._enqueue(
                f"{task}\n\n(From an email: {message.subject} — {message.sender})",
                priority=decision.priority,
            )
            actions.append(f"queued task: {task}")
            self._notify("task", f"From email: {task}", "/tasks")

        if not actions:
            actions.append(decision.category)

        self._store.mark_handled(
            message.id,
            message.sender,
            message.subject,
            category=decision.category,
            summary=decision.summary,
            actions=actions,
        )

    def start(self, interval: float = 120.0) -> None:
        def loop() -> None:
            while True:
                try:
                    self.tick()
                except Exception:
                    logger.exception("Inbox worker tick failed.")
                time.sleep(interval)

        threading.Thread(target=loop, daemon=True).start()
