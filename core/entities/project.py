from dataclasses import dataclass, field
from pathlib import Path

from core.entities.deliverable import Deliverable
from core.entities.methodology import Methodology
from core.entities.work_item import WorkItem


@dataclass
class Project:
    """
    Represents an executable project.

    A Project is created from an Execution Strategy and contains
    the work required to accomplish a Mission.
    """

    name: str
    goal: str
    workspace: Path
    methodology: Methodology

    work_items: list[WorkItem] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)

    def get_deliverable(self, filename: str) -> Deliverable | None:
        for deliverable in self.deliverables:
            if deliverable.latest_filename() == filename:
                return deliverable
        return None