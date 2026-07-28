from __future__ import annotations

from collections.abc import Sequence

from core.agents.agent_turn import AgentTurn
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.tools.tool import Tool


class AnthropicAgentProvider(AgentProvider):
    """
    Tool-using agent turns backed by the Anthropic (Claude) API.

    The counterpart to `OllamaAgentProvider`: it is handed the running history
    and the tool schemas and returns either tool calls or a final answer, so the
    task agent (the one that produces decks, documents and spreadsheets) can run
    on Claude. Opt in with `HYPERIUM_LLM_PROVIDER=anthropic`; Ollama is default.

    The interesting work is translation. The runner speaks one neutral message
    dialect (see `AgentProvider`); Anthropic wants another:

    - A neutral ``system`` message is not a message at all to Anthropic — it is
      the top-level ``system`` parameter. Every system message is collected out.
    - An assistant turn's ``tool_calls`` become ``tool_use`` content blocks, each
      needing an ``id``. The neutral dialect carries no ids, so they are
      synthesised per turn and the following tool results are matched to them by
      position — which is exactly how the runner appends them (each call's result
      immediately after, in order).
    - Consecutive neutral ``tool`` messages are merged into a single Anthropic
      user message of ``tool_result`` blocks, as the API requires.

    Like the text provider: SDK imported lazily (optional dependency), a `client`
    injectable for tests, thinking off by default for cost.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-8",
        api_key: str | None = None,
        max_tokens: int = 8192,
        timeout_seconds: float = 300.0,
        thinking: bool = False,
        client=None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        self._thinking = thinking

        if client is not None:
            self._client = client
        else:
            import anthropic

            self._client = anthropic.Anthropic(
                api_key=api_key, timeout=timeout_seconds
            )

    def chat(
        self,
        messages: Sequence[dict],
        tools: Sequence[Tool],
    ) -> AgentTurn:
        system, anthropic_messages = self._translate(messages)

        request = {
            "model": self._model,
            "max_tokens": self._max_tokens,
            "messages": anthropic_messages,
            "tools": [self._tool_schema(tool) for tool in tools],
        }
        if system:
            request["system"] = system
        if self._thinking:
            request["thinking"] = {"type": "adaptive"}

        message = self._client.messages.create(**request)

        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in message.content:
            kind = getattr(block, "type", None)
            if kind == "text":
                text_parts.append(getattr(block, "text", ""))
            elif kind == "tool_use":
                calls.append(
                    ToolCall(
                        name=block.name,
                        arguments=dict(getattr(block, "input", None) or {}),
                    )
                )

        content = "".join(text_parts).strip() or None
        return AgentTurn(content=content, tool_calls=calls)

    def _translate(self, messages: Sequence[dict]) -> tuple[str, list[dict]]:
        """Turn the neutral history into (system, Anthropic messages)."""
        system_parts: list[str] = []
        out: list[dict] = []
        pending_ids: list[str] = []
        turn = 0

        for message in messages:
            role = message["role"]

            if role == "system":
                if message.get("content"):
                    system_parts.append(message["content"])
                continue

            if role == "user":
                out.append({"role": "user", "content": message.get("content", "")})
                continue

            if role == "assistant":
                blocks: list[dict] = []
                text = message.get("content")
                if text:
                    blocks.append({"type": "text", "text": text})

                ids: list[str] = []
                for index, call in enumerate(message.get("tool_calls") or []):
                    tool_use_id = f"toolu_{turn}_{index}"
                    ids.append(tool_use_id)
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": tool_use_id,
                            "name": call["name"],
                            "input": call.get("arguments") or {},
                        }
                    )

                turn += 1
                pending_ids = ids  # results for this turn follow, in order
                out.append({"role": "assistant", "content": blocks or (text or "")})
                continue

            if role == "tool":
                # Match this result to the next unclaimed tool_use of the turn.
                tool_use_id = (
                    pending_ids.pop(0) if pending_ids else f"toolu_orphan_{turn}"
                )
                block = {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": message.get("content", ""),
                }
                # All results for one assistant turn go in one user message.
                if (
                    out
                    and out[-1]["role"] == "user"
                    and isinstance(out[-1]["content"], list)
                ):
                    out[-1]["content"].append(block)
                else:
                    out.append({"role": "user", "content": [block]})
                continue

        return "\n\n".join(system_parts), out

    def _tool_schema(self, tool: Tool) -> dict:
        """`Tool.schema()` is OpenAI-shaped; Anthropic wants its own shape."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters,
        }
