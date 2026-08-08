from __future__ import annotations

from dataclasses import dataclass, field

from core.agents.tool_call import ToolCall


@dataclass(frozen=True)
class AgentTurn:
    """
    One response from the model.

    Either it asks to run tools (`tool_calls` is non-empty) or it produces a
    final answer (`content`). A provider should not return both empty.
    """

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)
