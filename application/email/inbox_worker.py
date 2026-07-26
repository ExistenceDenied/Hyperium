from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from core.interfaces.mail_provider import MailProvider
from core.rules.rule import RuleSet

logger = logging.getLogger(__name__)


class InboxWorker:
    """
    Triages a mail folder on a clock, applies business rules, and acts.

    Triage (a model) decides what each message is; the rules (a deterministic
    decision table) decide what to do about it — draft or send, and whether to
    attach deliverables. Sending is doubly gated: a rule must ask for it and the
    outbound switch must be on, and even then the reply only goes back to the
    original sender. Work the mail implies becomes queued tasks. It reads only
    what is new since the last run, not the whole folder each time.
    """

    def __init__(
        self,
        provider: MailProvider,
        triage,
        responder,
        store,
        enqueue: Callable[..., object] = lambda prompt, **kw: None,
        rules: Callable[[], RuleSet] = lambda: RuleSet([]),
        can_send: Callable[[], bool] = lambda: False,
        deliverables: Callable[..., object] = lambda message: (),
        context: Callable[[], str] = lambda: "",
        notify: Callable[..., object] = lambda kind, text, link="": None,
    ) -> None:
        self._provider = provider
        self._triage = triage
        self._responder = responder
        self._store = store
        self._enqueue = enqueue
        self._rules = rules
        self._can_send = can_send
        self._deliverables = deliverables
        self._context = context
        self._notify = notify

    def tick(self) -> int:
        if not self._store.enabled:
            return 0

        folder = self._store.folder
        try:
            messages = self._provider.list_messages(folder, since=self._store.last_seen)
        except Exception:
            logger.exception("Could not read the '%s' folder.", folder)
            return 0

        handled = 0
        newest = self._store.last_seen
        for message in messages:
            if self._store.is_handled(message.id):
                continue
            try:
                self._handle(message)
            except Exception:
                logger.exception("Failed to handle %s.", message.id)
                continue
            if message.received_at and (newest is None or message.received_at > newest):
                newest = message.received_at
            handled += 1

        if newest is not None and newest != self._store.last_seen:
            self._store.set_last_seen(newest)
        return handled

    def _handle(self, message) -> None:
        context = self._context()
        decision = self._triage.classify(message, context)
        actions: list[str] = []
        reply_expected = decision.should_draft

        if reply_expected and not decision.tasks:
            # Nothing is being produced — reply now.
            actions.extend(self._reply(message, decision, context))
        elif decision.needs_attention:
            actions.append("flagged for you")
            self._notify(
                "email",
                f"Needs you: {message.subject} — {decision.summary}",
                "/email",
            )
        elif reply_expected and decision.tasks:
            # A single reply: it will be the delivery of what the tasks produce,
            # so there is no separate "we're preparing it" acknowledgement.
            actions.append("reply deferred to the deliverable")

        # Only a reply-worthy email routes its result back; internal tasks
        # (from an FYI or a flagged mail) run without emailing anyone.
        origin = (
            {
                "type": "email",
                "message_id": message.id,
                "sender": message.sender,
                "subject": message.subject,
            }
            if reply_expected
            else None
        )

        for task in decision.tasks:
            self._enqueue(
                f"{task}\n\n(From an email: {message.subject} — {message.sender})",
                priority=decision.priority,
                origin=origin,
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

    def _reply(self, message, decision, context) -> list[str]:
        body = self._responder.compose(message, context)
        ruled = self._rules().decide(self._inputs(message, decision))

        attachments = ()
        if ruled.is_true("attach_deliverables"):
            attachments = tuple(self._deliverables(message))

        want_send = ruled.get("delivery", "draft").strip().lower() == "send"
        actions: list[str] = []

        if want_send and self._can_send():
            self._provider.send_reply(message, body, attachments)
            fired = f" (rule: {', '.join(ruled.fired)})" if ruled.fired else ""
            actions.append("sent a reply" + fired)
            self._notify(
                "email",
                f"Sent a reply to {message.sender} — {message.reply_subject}",
                "/email",
            )
        else:
            self._provider.draft_reply(message, body, attachments)
            note = "drafted a reply"
            if want_send and not self._can_send():
                note += " (a rule wanted to send, but the outbound switch is off)"
            actions.append(note)
            self._notify(
                "email",
                f"Draft ready: {message.reply_subject} (to {message.sender})",
                "/email",
            )

        if attachments:
            actions.append(f"attached {len(attachments)} file(s)")
        return actions

    def _inputs(self, message, decision) -> dict:
        return {
            "sender": message.sender,
            "subject": message.subject,
            "category": decision.category,
            "priority": decision.priority,
            "confidence": str(decision.confidence),
        }

    def start(self) -> None:
        def loop() -> None:
            while True:
                try:
                    self.tick()
                except Exception:
                    logger.exception("Inbox worker tick failed.")
                # Re-read the interval each cycle, so a change on the Email page
                # takes effect on the next check without restarting the server.
                time.sleep(max(60, self._store.interval_minutes * 60))

        threading.Thread(target=loop, daemon=True).start()
