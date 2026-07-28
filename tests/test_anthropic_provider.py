from __future__ import annotations

from types import SimpleNamespace

from infrastructure.llm.anthropic_agent_provider import AnthropicAgentProvider
from infrastructure.llm.anthropic_provider import AnthropicProvider


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_use(name: str, arguments: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=name, input=arguments)


class FakeMessages:
    """Records the request and returns a canned message, standing in for the SDK."""

    def __init__(self, blocks):
        self._blocks = blocks
        self.last_request: dict | None = None

    def create(self, **request):
        self.last_request = request
        return SimpleNamespace(content=self._blocks)


class FakeClient:
    def __init__(self, blocks):
        self.messages = FakeMessages(blocks)


# ------------------------------------------------------------- text provider


def test_generate_joins_text_blocks_and_strips():
    client = FakeClient([_text("  Hello "), _text("world  ")])
    provider = AnthropicProvider(client=client)

    assert provider.generate("hi") == "Hello world"


def test_generate_ignores_non_text_blocks():
    client = FakeClient([_tool_use("noop", {}), _text("answer")])
    provider = AnthropicProvider(client=client)

    assert provider.generate("hi") == "answer"


def test_generate_returns_empty_on_a_textless_turn():
    # A refusal or thinking-only turn yields no text; "" lets the resilient
    # wrapper retry it as an empty result.
    client = FakeClient([_tool_use("noop", {})])
    provider = AnthropicProvider(client=client)

    assert provider.generate("hi") == ""


def test_generate_passes_model_system_and_thinking():
    client = FakeClient([_text("ok")])
    provider = AnthropicProvider(
        model="claude-haiku-4-5",
        max_tokens=1024,
        system="only json",
        thinking=True,
        client=client,
    )

    provider.generate("do it")
    request = client.messages.last_request

    assert request["model"] == "claude-haiku-4-5"
    assert request["max_tokens"] == 1024
    assert request["system"] == "only json"
    assert request["thinking"] == {"type": "adaptive"}
    assert request["messages"] == [{"role": "user", "content": "do it"}]


def test_generate_omits_system_and_thinking_by_default():
    client = FakeClient([_text("ok")])
    AnthropicProvider(client=client).generate("hi")
    request = client.messages.last_request

    assert "system" not in request
    assert "thinking" not in request


# ------------------------------------------------------------ agent provider


class _Tool:
    name = "write_file"
    description = "Write a file."
    parameters = {"type": "object", "properties": {"path": {"type": "string"}}}


def test_chat_reads_tool_use_and_text():
    client = FakeClient(
        [_text("thinking out loud"), _tool_use("write_file", {"path": "a.md"})]
    )
    provider = AnthropicAgentProvider(client=client)

    turn = provider.chat([{"role": "user", "content": "make a file"}], [_Tool()])

    assert turn.content == "thinking out loud"
    assert turn.wants_tools
    assert turn.tool_calls[0].name == "write_file"
    assert turn.tool_calls[0].arguments == {"path": "a.md"}


def test_chat_final_answer_has_no_tool_calls():
    client = FakeClient([_text("all done")])
    provider = AnthropicAgentProvider(client=client)

    turn = provider.chat([{"role": "user", "content": "hi"}], [_Tool()])

    assert turn.content == "all done"
    assert not turn.wants_tools


def test_chat_advertises_tools_in_anthropic_shape():
    client = FakeClient([_text("ok")])
    AnthropicAgentProvider(client=client).chat(
        [{"role": "user", "content": "hi"}], [_Tool()]
    )

    tools = client.messages.last_request["tools"]
    assert tools == [
        {
            "name": "write_file",
            "description": "Write a file.",
            "input_schema": _Tool.parameters,
        }
    ]


def test_translate_extracts_system_and_correlates_tool_results():
    client = FakeClient([_text("done")])
    provider = AnthropicAgentProvider(client=client)

    history = [
        {"role": "system", "content": "You are an agent."},
        {"role": "user", "content": "make two files"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"name": "write_file", "arguments": {"path": "a.md"}},
                {"name": "write_file", "arguments": {"path": "b.md"}},
            ],
        },
        {"role": "tool", "name": "write_file", "content": "wrote a.md"},
        {"role": "tool", "name": "write_file", "content": "wrote b.md"},
    ]

    provider.chat(history, [_Tool()])
    request = client.messages.last_request

    # System is lifted out of the message list into the top-level parameter.
    assert request["system"] == "You are an agent."

    messages = request["messages"]
    assert messages[0] == {"role": "user", "content": "make two files"}

    # The assistant turn carries two tool_use blocks with synthesised ids.
    tool_uses = messages[1]["content"]
    assert [b["type"] for b in tool_uses] == ["tool_use", "tool_use"]
    first_id, second_id = tool_uses[0]["id"], tool_uses[1]["id"]
    assert first_id != second_id

    # Both results land in a single following user message, matched by position.
    results = messages[2]
    assert results["role"] == "user"
    assert [b["tool_use_id"] for b in results["content"]] == [first_id, second_id]
    assert [b["content"] for b in results["content"]] == ["wrote a.md", "wrote b.md"]
