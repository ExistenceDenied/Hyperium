from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolCall:
    """A model's request to run one tool with concrete arguments."""

    name: str
    arguments: dict = field(default_factory=dict)
