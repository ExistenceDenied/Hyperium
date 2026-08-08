from __future__ import annotations

import json

import pytest

from core.email.email_message import EmailMessage
from infrastructure.email.ms365_mail import Ms365MailProvider


class _FakeCall:
    """Records tool calls and returns canned JSON, like an MCP call_tool."""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        value = self._responses.get(name, {})
        return json.dumps(value) if not isinstance(value, str) else value

    def names(self):
        return [name for name, _ in self.calls]

    def args_for(self, name):
        return next(a for n, a in self.calls if n == name)


def _msg():
    return EmailMessage(id="AAA", sender="c@acme.com", subject="Quote?", body="?")


def test_list_uses_mailfolderid_and_parses_graph_messages():
    call = _FakeCall(
        {
            "list-mail-folder-messages": {
                "value": [
                    {
                        "id": "AAA",
                        "subject": "Quote request",
                        "from": {"emailAddress": {"address": "client@acme.com"}},
                        "body": {"contentType": "text", "content": "Please quote."},
                    }
                ]
            }
        }
    )
    messages = Ms365MailProvider(call, limit=10).list_messages("Inbox")

    args = call.args_for("list-mail-folder-messages")
    assert args["mailFolderId"] == "inbox"
    assert "filter" not in args  # no watermark → no filter
    assert messages[0].sender == "client@acme.com"


def test_list_since_adds_a_received_after_filter():
    from datetime import datetime, timezone

    call = _FakeCall()
    Ms365MailProvider(call).list_messages(
        "Inbox", since=datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
    )

    args = call.args_for("list-mail-folder-messages")
    assert args["filter"] == "receivedDateTime gt 2026-07-26T12:00:00Z"


def test_custom_folder_is_resolved_to_its_id():
    call = _FakeCall(
        {"list-mail-folders": {"value": [{"id": "id-hy", "displayName": "Hyperium"}]}}
    )
    Ms365MailProvider(call).list_messages("Hyperium")

    assert call.args_for("list-mail-folder-messages")["mailFolderId"] == "id-hy"


def test_draft_reply_threads_onto_the_original_via_reply_draft():
    call = _FakeCall({"create-reply-draft": {"id": "draft-1"}})

    Ms365MailProvider(call).draft_reply(_msg(), "Here is the answer.")

    name, args = call.calls[0]
    assert name == "create-reply-draft"
    assert args["messageId"] == "AAA"  # threaded to the original
    assert args["body"] == {"Comment": "Here is the answer."}


def test_send_reply_without_attachments_sends_in_thread():
    call = _FakeCall()

    Ms365MailProvider(call).send_reply(_msg(), "On it.")

    name, args = call.calls[0]
    assert name == "reply-mail-message"  # sends to the original sender only
    assert args["messageId"] == "AAA"
    assert args["body"] == {"Comment": "On it."}


def test_send_reply_with_attachments_drafts_attaches_then_sends():
    call = _FakeCall({"create-reply-draft": {"id": "draft-9"}})

    Ms365MailProvider(call).send_reply(
        _msg(), "See attached.", attachments=[("quote.pdf", b"%PDF-1.4")]
    )

    assert call.names() == [
        "create-reply-draft",
        "add-mail-attachment",
        "send-draft-message",
    ]
    attach = call.args_for("add-mail-attachment")
    assert attach["messageId"] == "draft-9"
    assert attach["body"]["name"] == "quote.pdf"
    assert call.args_for("send-draft-message")["messageId"] == "draft-9"


def test_a_tool_error_response_is_raised_not_swallowed():
    def call(name, arguments):
        return "Error from tool 'reply-mail-message': MCP error -32602: bad input"

    with pytest.raises(RuntimeError):
        Ms365MailProvider(call).send_reply(_msg(), "reply")
