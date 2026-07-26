from __future__ import annotations

from datetime import datetime, timezone

from application.email.email_responder import EmailResponder
from application.email.inbox_worker import InboxWorker
from core.email.email_message import EmailMessage
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


def _message(mid="m1", subject="Quote request"):
    return EmailMessage(
        id=mid,
        sender="client@acme.com",
        subject=subject,
        body="Could you send a quote for 200 units?",
        received_at=datetime.now(timezone.utc),
    )


def test_reply_subject_is_prefixed_once():
    assert _message(subject="Hi").reply_subject == "Re: Hi"
    assert _message(subject="Re: Hi").reply_subject == "Re: Hi"


def test_the_mail_provider_offers_no_way_to_send():
    # Draft-only is a type guarantee: the port has no send method at all.
    assert not hasattr(MailProvider, "send")
    assert not any("send" in name.lower() for name in vars(MailProvider))


def test_responder_uses_business_memory(tmp_path):
    llm = _CannedLLM()
    responder = EmailResponder(llm)

    responder.compose(_message(), context="We charge £5 per unit.")

    assert "We charge £5 per unit." in llm.prompts[0]
    assert "Could you send a quote" in llm.prompts[0]


def test_worker_drafts_a_reply_for_new_mail_and_notifies(tmp_path):
    mail = _FakeMail([_message()])
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=True, folder="Hyperium")
    alerts = []

    worker = InboxWorker(
        mail,
        EmailResponder(_CannedLLM("Here is your quote.")),
        store,
        notify=lambda kind, text, link="": alerts.append((kind, text)),
    )

    drafted = worker.tick()

    assert drafted == 1
    assert mail.drafts == [("m1", "Here is your quote.")]
    assert store.is_handled("m1")
    assert alerts and alerts[0][0] == "email"


def test_worker_drafts_once_per_message(tmp_path):
    mail = _FakeMail([_message()])
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=True, folder="Hyperium")
    worker = InboxWorker(mail, EmailResponder(_CannedLLM()), store)

    assert worker.tick() == 1
    assert worker.tick() == 0  # already handled
    assert len(mail.drafts) == 1


def test_worker_does_nothing_while_disabled(tmp_path):
    mail = _FakeMail([_message()])
    store = InboxStore(tmp_path / "inbox.json")  # defaults to disabled
    worker = InboxWorker(mail, EmailResponder(_CannedLLM()), store)

    assert worker.tick() == 0
    assert mail.drafts == []


def test_store_round_trips_config_and_log(tmp_path):
    store = InboxStore(tmp_path / "inbox.json")
    store.configure(enabled=True, folder="Sales")
    store.mark_handled("x1", "a@b.com", "Hello")

    reloaded = InboxStore(tmp_path / "inbox.json")
    assert reloaded.enabled is True
    assert reloaded.folder == "Sales"
    assert reloaded.is_handled("x1")
    assert reloaded.handled()[0]["sender"] == "a@b.com"
