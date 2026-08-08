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
    # A plain question (no artifact requested), so the reply-path tests are not
    # intercepted by the deliverable safety net.
    return EmailMessage(
        id=mid,
        sender=sender,
        subject="Quick question",
        body="What are your opening hours on Saturday?",
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


def test_deliverable_detection_ignores_substring_matches():
    from application.email.inbox_worker import _is_deliverable_request

    # "airplane" contains "plan", "shareholder" contains "share" — must not fire.
    noise = EmailMessage(
        id="x", sender="a@b.com", subject="Airplane details",
        body="I wanted the airplane info for the shareholder meeting.",
    )
    assert _is_deliverable_request(noise) is False

    real = EmailMessage(
        id="y", sender="a@b.com", subject="Please send a report",
        body="Can you provide a report on Q3?",
    )
    assert _is_deliverable_request(real) is True


def test_a_deliverable_request_becomes_a_task_even_if_the_model_forgot(tmp_path):
    # The model said "reply" with no task; the email clearly asks for a template.
    mail = _FakeMail(
        [
            EmailMessage(
                id="m1",
                sender="krisleunis1@gmail.com",
                subject="McKinsey test strategy template",
                body="Please provide a test strategy template. Send asap.",
            )
        ]
    )
    queued: list = []

    _worker(
        mail,
        _store(tmp_path),
        TriageDecision(category="reply", tasks=[]),
        enqueue=lambda p, **kw: queued.append((p, kw)),
    ).tick()

    assert mail.drafts == []  # deferred to the delivery, not an empty ack
    assert len(queued) == 1
    assert "Produce the deliverable" in queued[0][0]
    assert queued[0][1]["origin"]["message_id"] == "m1"


def test_a_plain_question_still_gets_an_immediate_reply(tmp_path):
    # No artifact requested → no synthesised task → reply now.
    mail = _FakeMail(
        [
            EmailMessage(
                id="m2",
                sender="client@acme.com",
                subject="Opening hours?",
                body="What time do you open on Saturday?",
            )
        ]
    )
    queued: list = []

    _worker(
        mail,
        _store(tmp_path),
        TriageDecision(category="reply", tasks=[]),
        enqueue=lambda p, **kw: queued.append(p),
    ).tick()

    assert len(mail.drafts) == 1
    assert queued == []


def test_a_rule_overrides_the_triaged_category(tmp_path):
    # The model escalates, but a rule says mail from me is always a reply.
    mail = _FakeMail([_message(sender="krisleunis1@gmail.com")])
    rules = RuleSet(
        [
            Rule(
                name="mine-are-replies",
                conditions=[Condition("sender", "startsWith", "krisleunis")],
                outputs={"category": "reply"},
            )
        ]
    )

    _worker(
        mail,
        _store(tmp_path),
        TriageDecision(category="escalate"),
        rules=lambda: rules,
    ).tick()

    assert len(mail.drafts) == 1  # drafted a reply, not escalated


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


# ------------------------------------------- watermark (no dropped mail)


class _WindowMail(_FakeMail):
    """A mailbox that honours `since` and a fetch limit, oldest first."""

    def __init__(self, messages, limit=10):
        super().__init__(messages)
        self._all = sorted(messages, key=lambda m: m.received_at)
        self._limit = limit

    def list_messages(self, folder, since=None):
        self.since_calls.append(since)
        newer = [m for m in self._all if since is None or m.received_at > since]
        return newer[: self._limit]


class _FlakyTriage:
    """Triage that raises for a message the first time it is seen."""

    def __init__(self, fail_once_for):
        self._fail = set(fail_once_for)
        self._seen: dict = {}

    def classify(self, message, context=""):
        self._seen[message.id] = self._seen.get(message.id, 0) + 1
        if message.id in self._fail and self._seen[message.id] == 1:
            raise RuntimeError("transient triage failure")
        return TriageDecision(category="skip")


def _at(hour):
    return datetime(2026, 7, 26, hour, tzinfo=timezone.utc)


def _skip_worker(mail, store, triage=None):
    return InboxWorker(
        mail, triage or _FixedTriage(TriageDecision(category="skip")),
        EmailResponder(_CannedLLM()), store,
    )


def test_a_burst_larger_than_the_fetch_limit_is_not_dropped(tmp_path):
    msgs = [_message(mid=f"m{i}", when=_at(10 + i)) for i in range(3)]  # m0<m1<m2
    mail = _WindowMail(msgs, limit=2)  # can only see 2 per tick
    store = _store(tmp_path)
    worker = _skip_worker(mail, store)

    worker.tick()  # sees oldest 2 (m0, m1)
    assert store.is_handled("m0") and store.is_handled("m1")
    assert not store.is_handled("m2")  # not yet fetched

    worker.tick()  # watermark advanced → now sees m2
    assert store.is_handled("m2")


def test_a_transient_failure_does_not_skip_the_message(tmp_path):
    m0, m1, m2 = (_message(f"m{i}", when=_at(10 + i)) for i in range(3))
    mail = _WindowMail([m0, m1, m2])
    store = _store(tmp_path)
    worker = _skip_worker(mail, store, triage=_FlakyTriage(fail_once_for=["m1"]))

    worker.tick()  # m0 ok; m1 fails → stop; m2 not reached
    assert store.is_handled("m0")
    assert not store.is_handled("m1") and not store.is_handled("m2")
    assert store.last_seen == _at(10)  # watermark did NOT jump past the failure

    worker.tick()  # m1 retried (now succeeds), then m2
    assert store.is_handled("m1") and store.is_handled("m2")


def test_check_interval_is_configurable_and_clamped(tmp_path):
    store = InboxStore(tmp_path / "inbox.json")

    assert store.interval_minutes == 2  # sensible default

    store.configure(enabled=True, folder="Inbox", interval_minutes=15)
    assert InboxStore(tmp_path / "inbox.json").interval_minutes == 15

    store.configure(enabled=True, folder="Inbox", interval_minutes=0)
    assert InboxStore(tmp_path / "inbox.json").interval_minutes == 1  # never < 1
