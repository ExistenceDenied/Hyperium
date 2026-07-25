from __future__ import annotations

from application.agent.agent_runner import AgentRunner
from core.agents.agent_result import StopReason
from core.agents.agent_turn import AgentTurn
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.tools.tool import Tool


class ScriptedProvider(AgentProvider):
    """Returns a pre-set sequence of turns, recording what it was sent."""

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append([dict(message) for message in messages])
        return self._turns.pop(0)


class EchoTool(Tool):
    name = "echo"
    description = "Echo the text argument."
    parameters = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self):
        self.invocations = []

    def invoke(self, arguments):
        self.invocations.append(arguments)
        return f"echoed: {arguments.get('text')}"


def test_runner_executes_tool_then_returns_final_answer():
    tool = EchoTool()
    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="echo", arguments={"text": "hi"})]),
            AgentTurn(content="All done."),
        ]
    )
    runner = AgentRunner(provider, [tool])

    result = runner.run("say hi", system="be helpful")

    assert result.output == "All done."
    assert result.stop_reason is StopReason.COMPLETED
    assert tool.invocations == [{"text": "hi"}]
    assert len(result.steps) == 1
    assert result.steps[0].tool == "echo"
    assert result.steps[0].result == "echoed: hi"


def test_tool_result_is_fed_back_to_the_model():
    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="echo", arguments={"text": "x"})]),
            AgentTurn(content="done"),
        ]
    )
    runner = AgentRunner(provider, [EchoTool()])

    runner.run("go")

    # The second model call must include the tool's result as a tool message.
    second = provider.calls[1]
    assert any(
        message["role"] == "tool" and "echoed: x" in message["content"]
        for message in second
    )


def test_unknown_tool_is_reported_not_raised():
    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="nope", arguments={})]),
            AgentTurn(content="ok"),
        ]
    )
    runner = AgentRunner(provider, [])

    result = runner.run("go")

    assert result.output == "ok"
    assert "no tool named 'nope'" in result.steps[0].result


def test_a_raising_tool_is_surfaced_to_the_model():
    class Boom(Tool):
        name = "boom"
        description = "Always fails."
        parameters = {"type": "object", "properties": {}}

        def invoke(self, arguments):
            raise RuntimeError("kaboom")

    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="boom", arguments={})]),
            AgentTurn(content="recovered"),
        ]
    )
    runner = AgentRunner(provider, [Boom()])

    result = runner.run("go")

    assert result.output == "recovered"
    assert "kaboom" in result.steps[0].result


def test_iteration_cap_stops_a_looping_model():
    class Loop(AgentProvider):
        def chat(self, messages, tools):
            return AgentTurn(
                tool_calls=[ToolCall(name="echo", arguments={"text": "x"})]
            )

    runner = AgentRunner(Loop(), [EchoTool()], max_iterations=3)

    result = runner.run("go")

    assert result.stop_reason is StopReason.MAX_ITERATIONS
    assert len(result.steps) == 3
