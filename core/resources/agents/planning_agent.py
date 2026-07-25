from core.resources.agents.base_agent import BaseAgent
from core.entities.project import Project
from core.entities.work_item import WorkItem
from core.parser import parse_agent_result


class PlanningAgent(BaseAgent):

    def __init__(self):
        super().__init__("Planning Agent")

    @property
    def system_prompt(self) -> str:
        return """
You are an expert Project Planner.

Return ONLY valid JSON.
Do not use markdown.
Do not explain anything.

The JSON MUST have EXACTLY this structure:

{
  "project": "Project name",

  "deliverables": [
    {
      "name": "Requirements Document",
      "filename": "requirements.md",
      "owner": "Business Analyst"
    }
  ],

    "tasks": [
    {
        "title": "Gather requirements",
        "assigned_agent": "Business Analyst",
        "expected_outputs": [
        "requirements.md"
        ]
    }
    ]
}

Rules:
Supported agent roles (use ONLY these exact names):

- Business Analyst
- Enterprise Architect
- Solution Architect
- Developer
- Tester

Do NOT invent new roles.

Examples:
- Use "Developer" instead of "Lead Developer".
- Use "Tester" instead of "QA Engineer".
- Use "Business Analyst" instead of "Project Manager".
- Use "Business Analyst" instead of "Technical Writer".
- Use "Solution Architect" instead of "System Architect".
- deliverables is ALWAYS an array of OBJECTS.
- Never use strings for deliverables.
- Every deliverable has:
    - name
    - filename
    - owner

- tasks is ALWAYS an array of OBJECTS.
- Every task has:
    - title
    - assigned_agent
    - expected_outputs

- expected_outputs is ALWAYS an array of filenames.

Example:

"expected_outputs": [
    "requirements.md"
]

Only output JSON.
"""

    def prepare(self, project: Project, work_item: WorkItem):
        print("Preparing planning context...")

    def execute(self, project: Project, work_item: WorkItem):

        self.prepare(project, work_item)

        response = self.ask(work_item.title)
        print(response)

        result = parse_agent_result(response)

        if not self.validate(result):
            raise ValueError("Planning result is invalid.")

        return self.produce(result)

    def validate(self, result) -> bool:

        if result is None:
            return False

        if len(result.new_work_items) == 0:
            return False

        return True

    def produce(self, result):
        return result
