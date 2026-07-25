from abc import ABC, abstractmethod

from core.entities.project import Project
from core.entities.work_item import WorkItem
from services.llm_service import LLMService
from services.workspace_service import WorkspaceService


class BaseAgent(ABC):

    def __init__(self, role: str):
        self.role = role
        self.llm = LLMService()
        self.workspace = WorkspaceService()

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Returns the system prompt for this agent."""
        pass

    def ask(self, prompt: str) -> str:
        return self.llm.ask(
            system=self.system_prompt,
            user=prompt,
        )

    def prepare(self, project: Project, work_item: WorkItem) -> None:
        """Prepare the execution context."""
        pass

    @abstractmethod
    def execute(self, project: Project, work_item: WorkItem):
        """Execute the assigned work item."""
        pass

    def validate(self, result) -> bool:
        """Validate the execution result."""
        return True

    def produce(self, result):
        """Finalize and return the result."""
        return result
