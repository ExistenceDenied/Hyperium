from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

from core.email.triage import CATEGORIES
from core.interfaces.mail_provider import MailProvider
from core.rules.rule import RuleSet

logger = logging.getLogger(__name__)

# Words that signal a request to produce a file, and the verbs that ask for it.
# When both appear and the model extracted no task, we add one anyway — a local
# model often replies "I'll prepare it" without turning it into work.
_ARTIFACTS = (
    "template", "document", "presentation", "powerpoint", "ppt", "deck",
    "slide", "report", "proposal", "spreadsheet", "excel", "analysis", "plan",
    "summary", "letter", "quote", "invoice", "value case", "overview", "brief",
    "deliverable",
)
_REQUESTS = (
    "send", "provide", "prepare", "create", "make", "produce", "generate",
    "draft", "need", "want", "put together", "give me", "share", "build",
)


# How many times to retry a message that keeps failing before giving up on it,
# so one poison message cannot block the whole folder forever.
_MAX_ATTEMPTS = 3


def _later(current, candidate):
    """The later of two timestamps, tolerant of None and a missing candidate."""
    if candidate is None:
        return current
    if current is None:
        return candidate
    return candidate if candidate > current else current


def _is_deliverable_request(message) -> bool:
    text = f"{message.subject}\n{message.body}".lower()
    return any(a in text for a in _ARTIFACTS) and any(r in text for r in _REQUESTS)


def _fallback_task(message) -> str:
    return (
        "Produce the deliverable this email asks for and save it as a file — a "
        "Word document, a PowerPoint deck or an Excel spreadsheet, whichever "
        f"fits best.\n\nSubject: {message.subject}\n\nRequest:\n{message.body[:800]}"
    )


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
        self._failures: dict[str, int] = {}

    def tick(self) -> int:
        if not self._store.enabled:
            return 0

        folder = self._store.folder
        try:
            # Oldest first, so the watermark can only advance across a contiguous
            # run of handled mail — nothing older is ever jumped over.
            messages = self._provider.list_messages(folder, since=self._store.last_seen)
        except Exception:
            logger.exception("Could not read the '%s' folder.", folder)
            return 0

        handled = 0
        # `progress` advances only through messages we are sure are done. It stops
        # at the first still-failing message, so that message is refetched next
        # tick rather than silently skipped by the strict `gt` watermark filter.
        progress = self._store.last_seen
        for message in messages:
            if self._store.is_handled(message.id):
                progress = _later(progress, message.received_at)
                continue
            try:
                self._handle(message)
            except Exception:
                logger.exception("Failed to handle %s.", message.id)
                self._failures[message.id] = self._failures.get(message.id, 0) + 1
                if self._failures[message.id] < _MAX_ATTEMPTS:
                    break  # retry from here next tick; do not advance past it
                # Give up on a poison message so it cannot wedge the folder.
                self._store.mark_handled(
                    message.id, message.sender, message.subject,
                    category="failed",
                    actions=["gave up after repeated errors"],
                )
                progress = _later(progress, message.received_at)
                continue
            self._failures.pop(message.id, None)
            progress = _later(progress, message.received_at)
            handled += 1

        newest = progress
        if newest is not None and newest != self._store.last_seen:
            self._store.set_last_seen(newest)
        return handled

    def _handle(self, message) -> None:
        context = self._context()
        decision = self._triage.classify(message, context)
        # A rule may override the model's category — deterministic control over
        # triage (e.g. "mail from me is always a reply, never escalated").
        ruled = self._rules().decide(self._inputs(message, decision))
        actions: list[str] = []
        override = ruled.get("category")
        if override in CATEGORIES and override != decision.category:
            actions.append(f"category set to '{override}' by a rule")
            decision.category = override

        reply_expected = decision.should_draft

        # Safety net: a request to produce something must become a task, even if
        # the model only wrote a reply promising it. Otherwise nothing is made.
        if reply_expected and not decision.tasks and _is_deliverable_request(message):
            decision.tasks = [_fallback_task(message)]
            actions.append("added a deliverable task (the request implied one)")

        if reply_expected and not decision.tasks:
            # Nothing is being produced — reply now.
            actions.extend(self._reply(message, decision, context, ruled))
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

    def _reply(self, message, decision, context, ruled) -> list[str]:
        body = self._responder.compose(message, context)

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
