from __future__ import annotations

from application.agent.agent_runner import AgentRunner
from application.execution.activity_executor import LlmActivityExecutor
from application.execution.agent_activity_executor import AgentActivityExecutor
from application.project.project_builder import ProjectBuilder
from core.agents.agent_turn import AgentTurn
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.resources.ai_resource import AIResource
from core.resources.human_resource import HumanResource
from core.tools.tool import Tool
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)

# --------------------------------------------------- the closed OCP leak


def test_ai_resource_executes_autonomously():
    assert AIResource(name="x").executes_autonomously is True


def test_a_human_resource_does_not():
    assert HumanResource(name="Sam").executes_autonomously is False


# ------------------------------------------------------------ executors


def test_llm_executor_returns_a_single_completion():
    executor = LlmActivityExecutor(ScriptedLLM())

    content = executor.execute("Elicit learning needs", activity=None)

    assert content.startswith("## Learning needs")


class ReadThenWriteAgent(AgentProvider):
    """Uses a tool once, then writes the section — a minimal agent."""

    def __init__(self, content: str):
        self._content = content
        self.used_tool = False

    def chat(self, messages, tools):
        if not self.used_tool and tools:
            self.used_tool = True
            return AgentTurn(
                tool_calls=[ToolCall(name=tools[0].name, arguments={})]
            )
        return AgentTurn(content=self._content)


class FixedTool(Tool):
    name = "read_context"
    description = "Return some context."
    parameters = {"type": "object", "properties": {}}

    def invoke(self, arguments):
        return "the real context"


def test_agent_executor_returns_the_agents_output():
    agent = ReadThenWriteAgent("## Section\nGrounded in real files.")
    executor = AgentActivityExecutor(AgentRunner(agent, [FixedTool()]))

    content = executor.execute("Write the section", activity=None)

    assert content == "## Section\nGrounded in real files."
    assert agent.used_tool is True


# ----------------------------- the fold: a whole engagement, agentically


def test_an_engagement_runs_through_the_agentic_executor():
    """
    Drive a real engagement whose activities are executed by an agent, not a
    one-shot completion. The deliverable's content must be what the agent
    produced, proving the direct-task agent now powers the methodology path.
    """
    agent = ReadThenWriteAgent("## Learning needs\nGathered from the workspace.")
    executor = AgentActivityExecutor(AgentRunner(agent, [FixedTool()]))

    service = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        methodologies=FakeMethodologies(),
        activity_executor=executor,
    )

    project = service.start(build_mission(), resources=[build_consultant()])

    version = project.deliverable("requirements").latest_version()

    assert version is not None
    assert "Gathered from the workspace." in version.content
    assert agent.used_tool is True
