from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from core.agents.agent_turn import AgentTurn
from core.tools.tool import Tool


class AgentProvider(ABC):
    """
    A model that can hold a tool-using conversation.

    This is a wider contract than `LLMProvider.generate`, which returns text
    for a single prompt and cannot act. An `AgentProvider` is handed the
    running message history and the available tools, and either asks to call a
    tool or answers.

    It is a separate port on purpose: the deterministic deliverable pipeline
    depends only on `generate`, and must not be forced to grow a tool loop it
    does not use.

    Messages are provider-agnostic dicts. The runner emits four shapes and the
    provider translates them to its own wire format:

    - ``{"role": "system" | "user", "content": str}``
    - ``{"role": "assistant", "content": str,
         "tool_calls": [{"name": str, "arguments": dict}]}``
    - ``{"role": "tool", "name": str, "content": str}``
    """

    @abstractmethod
    def chat(
        self,
        messages: Sequence[dict],
        tools: Sequence[Tool],
    ) -> AgentTurn:
        """Advance the conversation by one model turn."""
        raise NotImplementedError
