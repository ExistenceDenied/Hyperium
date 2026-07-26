from __future__ import annotations

import json

from infrastructure.email.ms365_mail import Ms365MailProvider


class _FakeCall:
    """Records tool calls and returns canned JSON, like an MCP call_tool."""

    def __init__(self, responses=None):
        self.calls = []
        self._responses = responses or {}

    def __call__(self, name, arguments):
        self.calls.append((name, arguments))
        value = self._responses.get(name, {"value": []})
        return json.dumps(value) if not isinstance(value, str) else value


def test_list_uses_mailfolderid_and_parses_graph_messages():
    call = _FakeCall(
        {
            "list-mail-folder-messages": {
                "value": [
                    {
                        "id": "AAA",
                        "subject": "Quote request",
                        "receivedDateTime": "2026-07-24T09:12:52Z",
                        "from": {"emailAddress": {"address": "client@acme.com"}},
                        "body": {"contentType": "text", "content": "Please quote."},
                    }
                ]
            }
        }
    )
    provider = Ms365MailProvider(call, limit=10)

    messages = provider.list_messages("Inbox")

    name, args = call.calls[0]
    assert name == "list-mail-folder-messages"
    assert args["mailFolderId"] == "inbox"  # well-known name used directly
    assert args["top"] == 10
    assert len(messages) == 1
    assert messages[0].sender == "client@acme.com"
    assert messages[0].subject == "Quote request"
    assert messages[0].body == "Please quote."


def test_a_custom_folder_is_resolved_to_its_id():
    call = _FakeCall(
        {
            "list-mail-folders": {
                "value": [
                    {"id": "id-hyperium", "displayName": "Hyperium"},
                    {"id": "id-other", "displayName": "Other"},
                ]
            }
        }
    )
    provider = Ms365MailProvider(call)

    provider.list_messages("Hyperium")

    # It looks folders up, then lists messages by the resolved id.
    assert call.calls[0][0] == "list-mail-folders"
    assert call.calls[1][1]["mailFolderId"] == "id-hyperium"


def test_draft_reply_builds_a_graph_message_object():
    from core.email.email_message import EmailMessage

    call = _FakeCall()
    provider = Ms365MailProvider(call)
    message = EmailMessage(id="X", sender="a@b.com", subject="Hi", body="…")

    provider.create_draft_reply(message, "Here is the answer.")

    name, args = call.calls[0]
    assert name == "create-draft-email"
    payload = args["body"]  # a single Graph message object
    assert payload["subject"] == "Re: Hi"
    assert payload["body"] == {"contentType": "text", "content": "Here is the answer."}
    assert payload["toRecipients"] == [{"emailAddress": {"address": "a@b.com"}}]


def test_a_tool_error_response_is_raised_not_swallowed():
    import pytest

    from core.email.email_message import EmailMessage

    def call(name, arguments):
        return "Error from tool 'create-draft-email': MCP error -32602: bad input"

    provider = Ms365MailProvider(call)
    with pytest.raises(RuntimeError):
        provider.create_draft_reply(
            EmailMessage(id="X", sender="a@b.com", subject="Hi", body="…"), "reply"
        )
