from core.entities.project import Project
from core.entities.work_item import WorkItemStatus


class Scheduler:

    def next_task(self, project: Project):

        for work_item in project.work_items:

            if work_item.status in (
                WorkItemStatus.CREATED,
                WorkItemStatus.READY,
            ):
                work_item.status = WorkItemStatus.IN_PROGRESS
                return work_item

        return None
