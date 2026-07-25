from dataclasses import dataclass, field

from core.agent_type import AgentType
from core.entities.deliverable_status import DeliverableStatus
from core.entities.deliverable_version import DeliverableVersion


@dataclass
class Deliverable:

    name: str

    owner: AgentType

    status: DeliverableStatus = DeliverableStatus.DRAFT

    versions: list[DeliverableVersion] = field(default_factory=list)

    current_version: int = 1

    def latest_version(self) -> DeliverableVersion:

        if not self.versions:
            raise ValueError(f"Deliverable '{self.name}' has no versions.")

        return self.versions[-1]

    def latest_filename(self) -> str:

        return self.latest_version().filename

    def add_version(self, version: DeliverableVersion):

        self.versions.append(version)
        self.current_version = version.version