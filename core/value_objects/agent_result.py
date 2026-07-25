from dataclasses import dataclass, field

from core.entities.deliverable import Deliverable
from core.entities.work_item import WorkItem


@dataclass
class AgentResult:
    deliverables: list[Deliverable] = field(default_factory=list)

    new_work_items: list[WorkItem] = field(default_factory=list)

    observations: list[str] = field(default_factory=list)
