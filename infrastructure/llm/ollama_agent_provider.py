from __future__ import annotations

from collections.abc import Sequence

import ollama

from core.agents.agent_turn import AgentTurn
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.tools.tool import Tool


class OllamaAgentProvider(AgentProvider):
    """
    Tool-using agent turns backed by Ollama's native function calling.

    Unlike `OllamaProvider`, which sends one prompt and reads one string, this
    passes the running history and the tool schemas to `chat(..., tools=...)`
    and reads back either tool calls or a final answer. It requires a local
    model that supports tools (qwen3, llama3.1, mistral-nemo, ...).

    Thinking is disabled by default: qwen3 emits chain-of-thought that is not
    part of the answer and only slows a tool loop.
    """

    def __init__(
        self,
        model: str = "qwen3:latest",
        timeout_seconds: float = 300.0,
        temperature: float | None = None,
        host: str | None = None,
        think: bool = False,
    ) -> None:
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._think = think
        self._client = ollama.Client(host=host, timeout=timeout_seconds)

    def chat(
        self,
        messages: Sequence[dict],
        tools: Sequence[Tool],
    ) -> AgentTurn:
        options = {}
        if self._temperature is not None:
            options["temperature"] = self._temperature

        response = self._client.chat(
            model=self._model,
            messages=[self._to_ollama(message) for message in messages],
            tools=[tool.schema() for tool in tools],
            options=options or None,
            think=self._think,
        )

        # Attribute access, not subscript: Ollama's message model raises
        # KeyError for an unset field, so a turn with no tool calls would blow
        # up on `message["tool_calls"]`. getattr yields None as intended.
        message = response["message"]
        calls = [
            ToolCall(
                name=call.function.name,
                arguments=dict(call.function.arguments or {}),
            )
            for call in (getattr(message, "tool_calls", None) or [])
        ]

        content = getattr(message, "content", None) or None

        return AgentTurn(content=content, tool_calls=calls)

    def _to_ollama(self, message: dict) -> dict:
        """
        Translate a neutral message into the shape Ollama expects.

        The runner speaks a provider-agnostic dialect: a tool result carries a
        `name`, and an assistant turn carries plain `tool_calls`. Ollama wants
        `tool_name` on tool results and a `function` wrapper around each call.
        """
        role = message["role"]

        if role == "tool":
            return {
                "role": "tool",
                "content": message.get("content", ""),
                "tool_name": message.get("name", ""),
            }

        if role == "assistant" and message.get("tool_calls"):
            return {
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": [
                    {
                        "function": {
                            "name": call["name"],
                            "arguments": call["arguments"],
                        }
                    }
                    for call in message["tool_calls"]
                ],
            }

        return {"role": role, "content": message.get("content", "")}
