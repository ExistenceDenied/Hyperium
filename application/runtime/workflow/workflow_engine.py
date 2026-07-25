from core.entities.project import Project
from application.runtime.work_queue import WorkQueue
from core.entities.work_item import WorkItemStatus
from core.entities.work_item import WorkItem
from core.agent_type import AgentType


class WorkflowEngine:

    def __init__(self):
        self.queue = WorkQueue()

    def initialize(self, project: Project):

        self.queue.add_many(project.work_items)

    def next_work_item(self):

        while not self.queue.is_empty():

            work_item = self.queue.pop()

            if work_item.status in (
                WorkItemStatus.CREATED,
                WorkItemStatus.READY,
            ):
                return work_item

        return None

    def add_work_items(self, work_items: list[WorkItem]) -> None:
        self.queue.add_many(work_items)

    def create_review_work_item(self, work_item: WorkItem) -> WorkItem:

        return WorkItem(
            title=f"Review - {work_item.title}",
            assigned_agent=AgentType.REVIEWER,
            objective=f"Review the deliverables created by '{work_item.title}'",
            input_files=work_item.expected_outputs,
        )