from core.resources.agents.base_agent import BaseAgent
from core.entities.deliverable import Deliverable
from core.entities.project import Project
from core.entities.work_item import WorkItem
from core.value_objects.agent_result import AgentResult


class DeveloperAgent(BaseAgent):

    def __init__(self):
        super().__init__("Developer")

    @property
    def system_prompt(self):
        return """
You are a senior software developer.

Produce a technical implementation document in Markdown.

Only output Markdown.
"""

    def execute(self, project: Project, work_item: WorkItem):

        markdown = self.ask(work_item.title)

        output = self.workspace.write(
            project.workspace,
            "implementation.md",
            markdown,
        )

        deliverable = Deliverable(
            name="Implementation Document",
            filename=output.name,
            owner=self.role,
        )

        return AgentResult(
            deliverables=[deliverable],
            new_work_items=[],
            observations=[],
        )
