from __future__ import annotations

from application.agent.agent_runner import AgentRunner
from application.execution.activity_executor import ActivityExecutor
from core.execution.activity import Activity

ACTIVITY_SYSTEM = (
    "You are producing one section of a professional consulting deliverable. "
    "Use your tools to ground the content in real information — read the "
    "relevant files, fetch the sources you are pointed to — rather than "
    "inventing facts. Then write the section exactly as the instructions ask, "
    "and return only the finished section, with no commentary."
)


class AgentActivityExecutor(ActivityExecutor):
    """
    Produces an activity's content with a tool-using agent.

    The activity's built prompt becomes the agent's task, so the persona,
    upstream work and template structure the engine assembled are all honoured
    — the agent simply gets to gather real information with its tools before
    writing. This is what folds the direct-task agent into the methodology
    pipeline: a whole engagement is now executed by agents, not one-shot
    completions, without changing what work the methodology decides on.
    """

    def __init__(self, runner: AgentRunner) -> None:
        self._runner = runner

    def execute(self, prompt: str, activity: Activity) -> str:
        return self._runner.run(prompt, system=ACTIVITY_SYSTEM).output
