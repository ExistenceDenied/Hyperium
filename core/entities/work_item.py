from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class WorkItemStatus(str, Enum):
    CREATED = "Created"
    READY = "Ready"
    IN_PROGRESS = "In Progress"
    UNDER_REVIEW = "Under Review"
    APPROVED = "Approved"
    COMPLETED = "Completed"


@dataclass
class WorkItem:
    title: str
    assigned_agent: str

    id: str = field(default_factory=lambda: str(uuid4()))

    objective: str = ""

    status: WorkItemStatus = WorkItemStatus.CREATED

    priority: int = 100

    input_files: list[str] = field(default_factory=list)

    expected_outputs: list[str] = field(default_factory=list)

    output_files: list[str] = field(default_factory=list)

    dependencies: list[str] = field(default_factory=list)
