from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class StopReason(Enum):
    """Why the agent loop ended."""

    COMPLETED = "completed"  # the model produced a final answer
    MAX_ITERATIONS = "max_iterations"  # the loop hit its step cap first


@dataclass(frozen=True)
class AgentStep:
    """One tool invocation and what it returned — the audit trail of a run."""

    tool: str
    arguments: dict
    result: str


@dataclass(frozen=True)
class AgentResult:
    """The outcome of running a task: the answer, plus every step taken."""

    output: str
    steps: list[AgentStep] = field(default_factory=list)
    stop_reason: StopReason = StopReason.COMPLETED
