from __future__ import annotations

from application.email.email_delivery import EmailDelivery
from core.interfaces.mail_provider import MailProvider
from core.rules.rule import Condition, Rule, RuleSet


class _FakeMail(MailProvider):
    def __init__(self):
        self.drafts = []
        self.sent = []

    def list_messages(self, folder, since=None):
        return []

    def draft_reply(self, message, body, attachments=()):
        self.drafts.append((message.id, body, tuple(attachments)))

    def send_reply(self, message, body, attachments=()):
        self.sent.append((message.id, body, tuple(attachments)))


_ORIGIN = {"type": "email", "message_id": "m1", "sender": "a@b.com", "subject": "Deck?"}


def _a_deck(tmp_path):
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(b"PPTXDATA")
    return [str(deck)]


def test_delivers_as_a_draft_with_the_file_attached_by_default(tmp_path):
    mail = _FakeMail()
    ok = EmailDelivery(mail).deliver(_ORIGIN, _a_deck(tmp_path))

    assert ok is True
    assert mail.sent == []
    mid, body, attachments = mail.drafts[0]
    assert mid == "m1"
    assert attachments == (("deck.pptx", b"PPTXDATA"),)
    assert "deck.pptx" in body


def test_only_the_named_deliverables_are_attached_not_the_whole_folder(tmp_path):
    # A scratch file sitting in the same folder must NOT be emailed out.
    (tmp_path / "scratch-notes.txt").write_bytes(b"internal notes")
    mail = _FakeMail()

    EmailDelivery(mail).deliver(_ORIGIN, _a_deck(tmp_path))

    names = [name for name, _ in mail.drafts[0][2]]
    assert names == ["deck.pptx"]  # scratch-notes.txt is not attached


def test_sends_when_a_rule_allows_and_the_switch_is_on(tmp_path):
    mail = _FakeMail()
    rules = RuleSet(
        [Rule(name="trusted", conditions=[Condition("sender", "startsWith", "a@")],
              outputs={"delivery": "send"})]
    )

    EmailDelivery(mail, rules=lambda: rules, can_send=lambda: True).deliver(
        _ORIGIN, _a_deck(tmp_path)
    )

    assert len(mail.sent) == 1
    assert mail.drafts == []


def test_kill_switch_keeps_it_a_draft_even_if_a_rule_sends(tmp_path):
    mail = _FakeMail()
    rules = RuleSet([Rule(name="trusted", outputs={"delivery": "send"})])

    EmailDelivery(mail, rules=lambda: rules, can_send=lambda: False).deliver(
        _ORIGIN, _a_deck(tmp_path)
    )

    assert mail.sent == []
    assert len(mail.drafts) == 1


def test_nothing_produced_means_no_delivery(tmp_path):
    mail = _FakeMail()
    assert EmailDelivery(mail).deliver(_ORIGIN, []) is False
    assert mail.drafts == [] and mail.sent == []


def test_a_non_email_origin_is_ignored(tmp_path):
    mail = _FakeMail()
    assert EmailDelivery(mail).deliver({"type": "other"}, []) is False
