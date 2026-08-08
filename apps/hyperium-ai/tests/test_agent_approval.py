from __future__ import annotations

from application.agent.agent_runner import AgentRunner
from application.agent.approval_policies import AutoApproveApprover
from core.agents.agent_turn import AgentTurn
from core.agents.approval import ApprovalDecision
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.interfaces.approver import Approver
from core.tools.tool import Tool


class ScriptedProvider(AgentProvider):
    def __init__(self, turns):
        self._turns = list(turns)

    def chat(self, messages, tools):
        return self._turns.pop(0)


class RecordingTool(Tool):
    name = "act"
    description = "A side-effecting tool."
    parameters = {"type": "object", "properties": {}}
    requires_approval = True

    def __init__(self):
        self.performed = False

    def preview(self, arguments):
        return "perform the irreversible act"

    def invoke(self, arguments):
        self.performed = True
        return "done"


def _run_once(tool, approver):
    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="act", arguments={})]),
            AgentTurn(content="finished"),
        ]
    )
    runner = AgentRunner(provider, [tool], approver=approver)
    return runner.run("go")


def test_side_effect_is_denied_without_an_approver():
    tool = RecordingTool()

    result = _run_once(tool, approver=None)

    assert tool.performed is False
    assert "Denied by the operator" in result.steps[0].result


def test_side_effect_runs_when_approved():
    tool = RecordingTool()

    result = _run_once(tool, approver=AutoApproveApprover())

    assert tool.performed is True
    assert result.steps[0].result == "done"


def test_denial_reason_is_fed_back_to_the_model():
    class Refuser(Approver):
        def review(self, request):
            # The preview must reach the approver so a human sees the effect.
            assert request.preview == "perform the irreversible act"
            return ApprovalDecision.deny("too risky")

    tool = RecordingTool()

    result = _run_once(tool, approver=Refuser())

    assert tool.performed is False
    assert "too risky" in result.steps[0].result


def test_read_only_tools_never_reach_the_approver():
    class Exploding(Approver):
        def review(self, request):
            raise AssertionError("a read-only tool must not be gated")

    class Reader(Tool):
        name = "read"
        description = "Read-only."
        parameters = {"type": "object", "properties": {}}

        def invoke(self, arguments):
            return "observed"

    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="read", arguments={})]),
            AgentTurn(content="ok"),
        ]
    )
    runner = AgentRunner(provider, [Reader()], approver=Exploding())

    result = runner.run("go")

    assert result.steps[0].result == "observed"
