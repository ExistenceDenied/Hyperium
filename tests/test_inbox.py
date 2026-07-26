from __future__ import annotations

from datetime import datetime, timezone

from application.email.email_responder import EmailResponder
from application.email.inbox_worker import InboxWorker
from core.email.email_message import EmailMessage
from core.email.triage import TriageDecision
from core.interfaces.llm_provider import LLMProvider
from core.interfaces.mail_provider import MailProvider
from core.rules.rule import Condition, Rule, RuleSet
from infrastructure.email.inbox_store import InboxStore


class _FakeMail(MailProvider):
    def __init__(self, messages):
        self._messages = messages
        self.drafts: list = []
        self.sent: list = []
        self.since_calls: list = []

    def list_messages(self, folder, since=None):
        self.since_calls.append(since)
        return list(self._messages)

    def draft_reply(self, message, body, attachments=()):
        self.drafts.append((message.id, body, tuple(attachments)))

    def send_reply(self, message, body, attachments=()):
        self.sent.append((message.id, body, tuple(attachments)))


class _CannedLLM(LLMProvider):
    def generate(self, prompt):
        return "Here is your quote."


class _FixedTriage:
    def __init__(self, decision):
        self.decision = decision

    def classify(self, message, context=""):
        return self.decision


def _message(mid="m1", sender="client@acme.com", when=None):
    return EmailMessage(
        id=mid,
        sender=sender,
        subject="Quote request",
        body="Could you send a quote?",
        received_at=when or datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc),
    )


def _store(tmp_path, enabled=True):
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=enabled, folder="Hyperium")
    return store


def _worker(mail, store, decision, **kw):
    return InboxWorker(
        mail,
        _FixedTriage(decision),
        EmailResponder(_CannedLLM()),
        store,
        **kw,
    )


_REPLY = TriageDecision(category="reply")


def test_reply_defaults_to_a_draft(tmp_path):
    mail = _FakeMail([_message()])

    _worker(mail, _store(tmp_path), _REPLY).tick()

    assert len(mail.drafts) == 1
    assert mail.sent == []


def test_a_rule_promotes_a_reply_to_a_real_send(tmp_path):
    mail = _FakeMail([_message(sender="kris.leunis@hyperium.be")])
    rules = RuleSet(
        [
            Rule(
                name="trusted",
                conditions=[Condition("sender", "startsWith", "kris.leunis")],
                outputs={"delivery": "send"},
            )
        ]
    )

    _worker(
        mail, _store(tmp_path), _REPLY, rules=lambda: rules, can_send=lambda: True
    ).tick()

    assert len(mail.sent) == 1
    assert mail.drafts == []


def test_the_kill_switch_forces_a_draft_even_when_a_rule_says_send(tmp_path):
    mail = _FakeMail([_message(sender="kris.leunis@hyperium.be")])
    rules = RuleSet(
        [
            Rule(
                name="trusted",
                conditions=[Condition("sender", "startsWith", "kris.leunis")],
                outputs={"delivery": "send"},
            )
        ]
    )

    # can_send is False → outbound switch off → never sends.
    _worker(
        mail, _store(tmp_path), _REPLY, rules=lambda: rules, can_send=lambda: False
    ).tick()

    assert mail.sent == []
    assert len(mail.drafts) == 1


def test_a_non_matching_sender_is_not_sent(tmp_path):
    mail = _FakeMail([_message(sender="stranger@example.com")])
    rules = RuleSet(
        [
            Rule(
                name="trusted",
                conditions=[Condition("sender", "startsWith", "kris.leunis")],
                outputs={"delivery": "send"},
            )
        ]
    )

    _worker(
        mail, _store(tmp_path), _REPLY, rules=lambda: rules, can_send=lambda: True
    ).tick()

    assert mail.sent == []
    assert len(mail.drafts) == 1


def test_attach_deliverables_rule_attaches_files(tmp_path):
    mail = _FakeMail([_message()])
    rules = RuleSet(
        [Rule(name="always-attach", outputs={"attach_deliverables": "true"})]
    )

    _worker(
        mail,
        _store(tmp_path),
        _REPLY,
        rules=lambda: rules,
        deliverables=lambda m: [("report.xlsx", b"data")],
    ).tick()

    assert mail.drafts[0][2] == (("report.xlsx", b"data"),)


def test_a_reply_that_spawns_a_task_defers_to_a_single_delivery(tmp_path):
    mail = _FakeMail([_message()])
    queued: list = []
    decision = TriageDecision(category="reply", tasks=["Prepare a deck"])

    _worker(
        mail, _store(tmp_path), decision, enqueue=lambda p, **kw: queued.append(kw)
    ).tick()

    # No immediate acknowledgement — the one reply will be the delivery.
    assert mail.drafts == [] and mail.sent == []
    # The task carries the email origin so the delivery can reply to it.
    assert queued[0]["origin"]["message_id"] == "m1"


def test_an_internal_task_from_an_fyi_carries_no_origin(tmp_path):
    mail = _FakeMail([_message()])
    queued: list = []
    decision = TriageDecision(category="fyi", tasks=["Log the enquiry"])

    _worker(
        mail, _store(tmp_path), decision, enqueue=lambda p, **kw: queued.append(kw)
    ).tick()

    assert queued[0]["origin"] is None  # not reply-worthy → nobody is emailed


def test_implied_tasks_are_queued(tmp_path):
    mail = _FakeMail([_message()])
    queued: list = []
    decision = TriageDecision(
        category="fyi", priority="high", tasks=["Prepare a quote"]
    )

    _worker(
        mail, _store(tmp_path), decision, enqueue=lambda p, **kw: queued.append((p, kw))
    ).tick()

    assert len(queued) == 1
    assert queued[0][1]["priority"] == "high"


def test_only_new_mail_is_fetched_and_the_watermark_advances(tmp_path):
    when = datetime(2026, 7, 26, 10, 0, tzinfo=timezone.utc)
    mail = _FakeMail([_message(when=when)])
    store = _store(tmp_path)

    _worker(mail, store, _REPLY).tick()

    assert mail.since_calls == [None]  # first run: no watermark
    assert store.last_seen == when  # advanced to the newest handled

    # A second tick asks only for mail newer than the watermark.
    mail.since_calls.clear()
    _worker(mail, store, _REPLY).tick()
    assert mail.since_calls == [when]


def test_worker_does_nothing_while_disabled(tmp_path):
    mail = _FakeMail([_message()])

    assert _worker(mail, _store(tmp_path, enabled=False), _REPLY).tick() == 0
    assert mail.drafts == [] and mail.sent == []


def test_check_interval_is_configurable_and_clamped(tmp_path):
    store = InboxStore(tmp_path / "inbox.json")

    assert store.interval_minutes == 2  # sensible default

    store.configure(enabled=True, folder="Inbox", interval_minutes=15)
    assert InboxStore(tmp_path / "inbox.json").interval_minutes == 15

    store.configure(enabled=True, folder="Inbox", interval_minutes=0)
    assert InboxStore(tmp_path / "inbox.json").interval_minutes == 1  # never < 1
