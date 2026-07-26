from __future__ import annotations

from datetime import datetime, timezone

from application.email.email_responder import EmailResponder
from application.email.inbox_worker import InboxWorker
from core.email.email_message import EmailMessage
from core.email.triage import TriageDecision
from core.interfaces.llm_provider import LLMProvider
from core.interfaces.mail_provider import MailProvider
from infrastructure.email.inbox_store import InboxStore


class _FakeMail(MailProvider):
    """A simulated mailbox that records drafts and, by design, cannot send."""

    def __init__(self, messages):
        self._messages = messages
        self.drafts: list[tuple[str, str]] = []

    def list_messages(self, folder):
        return list(self._messages)

    def create_draft_reply(self, message, body):
        self.drafts.append((message.id, body))


class _CannedLLM(LLMProvider):
    def __init__(self, reply="Thanks for your email — happy to help."):
        self.reply = reply
        self.prompts: list[str] = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.reply


class _FixedTriage:
    """Returns a preset decision, so worker routing can be tested in isolation."""

    def __init__(self, decision):
        self.decision = decision

    def classify(self, message, context=""):
        return self.decision


def _message(mid="m1", subject="Quote request"):
    return EmailMessage(
        id=mid,
        sender="client@acme.com",
        subject=subject,
        body="Could you send a quote for 200 units?",
        received_at=datetime.now(timezone.utc),
    )


def _worker(mail, store, decision, enqueue=None, alerts=None):
    sink = alerts if alerts is not None else []
    return InboxWorker(
        mail,
        _FixedTriage(decision),
        EmailResponder(_CannedLLM("Here is your quote.")),
        store,
        enqueue=enqueue or (lambda prompt, **kw: None),
        notify=(lambda kind, text, link="": sink.append((kind, text))),
    )


def _store(tmp_path, enabled=True):
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=enabled, folder="Hyperium")
    return store


def test_reply_subject_is_prefixed_once():
    assert _message(subject="Hi").reply_subject == "Re: Hi"
    assert _message(subject="Re: Hi").reply_subject == "Re: Hi"


def test_the_mail_provider_offers_no_way_to_send():
    assert not hasattr(MailProvider, "send")
    assert not any("send" in name.lower() for name in vars(MailProvider))


def test_responder_uses_business_memory():
    llm = _CannedLLM()
    EmailResponder(llm).compose(_message(), context="We charge £5 per unit.")
    assert "We charge £5 per unit." in llm.prompts[0]


def test_reply_category_drafts_and_notifies(tmp_path):
    mail = _FakeMail([_message()])
    alerts: list = []
    worker = _worker(
        mail, _store(tmp_path), TriageDecision(category="reply"), alerts=alerts
    )

    assert worker.tick() == 1
    assert mail.drafts == [("m1", "Here is your quote.")]
    assert any(kind == "email" for kind, _ in alerts)


def test_escalate_category_flags_without_drafting(tmp_path):
    mail = _FakeMail([_message()])
    alerts: list = []
    worker = _worker(
        mail,
        _store(tmp_path),
        TriageDecision(category="escalate", summary="A complaint"),
        alerts=alerts,
    )

    assert worker.tick() == 1
    assert mail.drafts == []  # no draft for something needing the owner
    assert any("Needs you" in text for _, text in alerts)


def test_skip_category_does_nothing_but_is_recorded(tmp_path):
    mail = _FakeMail([_message(subject="Newsletter")])
    store = _store(tmp_path)
    worker = _worker(mail, store, TriageDecision(category="skip"))

    assert worker.tick() == 1
    assert mail.drafts == []
    assert store.handled()[0]["category"] == "skip"


def test_implied_tasks_are_queued_for_any_category(tmp_path):
    mail = _FakeMail([_message()])
    queued: list = []
    decision = TriageDecision(
        category="reply",
        priority="high",
        tasks=["Prepare a quote for 200 units", "Add Acme to the CRM"],
    )
    worker = _worker(
        mail,
        _store(tmp_path),
        decision,
        enqueue=lambda prompt, **kw: queued.append((prompt, kw)),
    )

    worker.tick()

    assert len(queued) == 2
    assert "Prepare a quote for 200 units" in queued[0][0]
    assert queued[0][1]["priority"] == "high"


def test_worker_handles_each_message_once(tmp_path):
    mail = _FakeMail([_message()])
    store = _store(tmp_path)
    worker = _worker(mail, store, TriageDecision(category="reply"))

    assert worker.tick() == 1
    assert worker.tick() == 0
    assert len(mail.drafts) == 1


def test_worker_does_nothing_while_disabled(tmp_path):
    mail = _FakeMail([_message()])
    worker = _worker(mail, _store(tmp_path, enabled=False), TriageDecision())

    assert worker.tick() == 0
    assert mail.drafts == []


def test_store_round_trips_config_and_log(tmp_path):
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=True, folder="Sales")
    store.mark_handled("x1", "a@b.com", "Hello", category="reply", actions=["drafted"])

    reloaded = InboxStore(tmp_path / "inbox.json")
    assert reloaded.enabled is True
    assert reloaded.folder == "Sales"
    assert reloaded.is_handled("x1")
    assert reloaded.handled()[0]["category"] == "reply"
