from pathlib import Path

from core.agent_type import AgentType
from core.entities.methodology import Methodology
from core.entities.project import Project
from core.entities.work_item import WorkItem, WorkItemStatus
from application.runtime.scheduler import Scheduler


def test_scheduler_returns_first_ready_work_item():
    scheduler = Scheduler()

    methodology = Methodology(
        name="Test Methodology",
        description="Methodology used for testing."
    )

    project = Project(
        name="Test",
        goal="Test",
        workspace=Path("."),
        methodology=methodology,
    )

    project.work_items.append(
        WorkItem(
            title="Work Item 1",
            assigned_agent=AgentType.BUSINESS_ANALYST,
            objective="Test scheduler",
            status=WorkItemStatus.CREATED,
        )
    )

    work_item = scheduler.next_task(project)

    assert work_item is not None
    assert work_item.title == "Work Item 1"
    assert work_item.status == WorkItemStatus.IN_PROGRESS