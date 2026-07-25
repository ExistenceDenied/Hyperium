from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence

from core.agents.agent_result import AgentResult, AgentStep, StopReason
from core.agents.agent_turn import AgentTurn
from core.interfaces.agent_provider import AgentProvider
from core.tools.tool import Tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_ITERATIONS = 12


class AgentRunner:
    """
    Drives a task to completion by looping a model against a set of tools.

    The loop is the whole point: the model proposes a tool call, the runner
    executes it and feeds the result back, and this repeats until the model
    answers or a hard iteration cap is hit. The cap is not optional — a local
    model can loop on a tool indefinitely, and an unbounded agent is a hang.
    """

    def __init__(
        self,
        provider: AgentProvider,
        tools: Sequence[Tool],
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> None:
        self._provider = provider
        self._tools: Mapping[str, Tool] = {tool.name: tool for tool in tools}
        self._max_iterations = max_iterations

    def run(self, task: str, system: str | None = None) -> AgentResult:
        messages: list[dict] = []

        if system:
            messages.append({"role": "system", "content": system})

        messages.append({"role": "user", "content": task})

        steps: list[AgentStep] = []
        tools = list(self._tools.values())

        for iteration in range(1, self._max_iterations + 1):
            turn = self._provider.chat(messages, tools)

            if not turn.wants_tools:
                return AgentResult(
                    output=(turn.content or "").strip(),
                    steps=steps,
                    stop_reason=StopReason.COMPLETED,
                )

            messages.append(self._assistant_message(turn))

            for call in turn.tool_calls:
                result = self._invoke(call.name, call.arguments)
                steps.append(
                    AgentStep(
                        tool=call.name,
                        arguments=call.arguments,
                        result=result,
                    )
                )
                messages.append(
                    {"role": "tool", "name": call.name, "content": result}
                )
                logger.info(
                    "Tool '%s' called on iteration %s.", call.name, iteration
                )

        return AgentResult(
            output=self._exhausted_message(),
            steps=steps,
            stop_reason=StopReason.MAX_ITERATIONS,
        )

    def _assistant_message(self, turn: AgentTurn) -> dict:
        return {
            "role": "assistant",
            "content": turn.content or "",
            "tool_calls": [
                {"name": call.name, "arguments": call.arguments}
                for call in turn.tool_calls
            ],
        }

    def _invoke(self, name: str, arguments: dict) -> str:
        tool = self._tools.get(name)

        if tool is None:
            # Handed back to the model rather than raised: the model chose the
            # name, and telling it the tool does not exist lets it recover.
            return f"Error: no tool named '{name}' is available."

        try:
            return tool.invoke(arguments)
        except Exception as error:
            # A tool failure is information for the model, not a crash for the
            # run. It is logged in full and summarised back into the loop.
            logger.exception("Tool '%s' raised.", name)
            return f"Error: tool '{name}' failed: {error}"

    def _exhausted_message(self) -> str:
        return (
            "The task was not completed within the allowed number of steps. "
            "The findings gathered so far are in the tool results above."
        )
