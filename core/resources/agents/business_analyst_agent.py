from core.resources.agents.base_agent import BaseAgent
from core.entities.deliverable import Deliverable
from core.entities.project import Project
from core.entities.work_item import WorkItem
from core.value_objects.agent_result import AgentResult
from datetime import datetime
from core.entities.deliverable_version import DeliverableVersion

class BusinessAnalystAgent(BaseAgent):

    def __init__(self):
        super().__init__("Business Analyst")

    @property
    def system_prompt(self):
        return """
You are a senior Business Analyst.

Write a professional requirements document in Markdown.

Only output Markdown.
"""

    def execute(self, project: Project, work_item: WorkItem):

        markdown = self.ask(work_item.title)

        if not work_item.expected_outputs:
            raise ValueError(
                f"Work item '{work_item.title}' has no expected outputs."
            )

        filename = work_item.expected_outputs[0]

        output = self.workspace.write(
            project.workspace,
            filename,
            markdown,
        )

        version = DeliverableVersion(
            version=1,
            filename=output.name,
            created_by=self.role,
            created_at=datetime.now(),
        )

        deliverable = Deliverable(
            name="Requirements Document",
            owner=self.role,
            versions=[version],
        )

        return AgentResult(
            deliverables=[deliverable],
            new_work_items=[],
            observations=[],
        )
