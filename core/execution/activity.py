from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.capabilities.capability_requirement import CapabilityRequirement
from core.execution.activity_status import ActivityStatus


@dataclass
class Activity:
    """
    Represents a unit of work required to produce a deliverable.

    `key` is the stable business identifier. Dependencies are expressed
    between keys rather than UUIDs so that a plan stays readable, survives
    serialisation, and can be authored by a methodology as easily as by an
    analysis step.
    """

    key: str = ""
    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    required_capabilities: set[CapabilityRequirement] = field(default_factory=set)
    depends_on: set[str] = field(default_factory=set)
    status: ActivityStatus = ActivityStatus.PENDING
    output: str | None = None
    technique: str | None = None

    def requires(self, requirement: CapabilityRequirement) -> None:
        self.required_capabilities.add(requirement)

    def requires_all(
        self,
        requirements: set[CapabilityRequirement],
    ) -> None:
        self.required_capabilities.update(requirements)

    def depends_upon(self, key: str) -> None:
        self.depends_on.add(key)

    @property
    def is_completed(self) -> bool:
        return self.status is ActivityStatus.COMPLETED

    def complete(self, output: str) -> None:
        self.output = output
        self.status = ActivityStatus.COMPLETED

    def fail(self) -> None:
        self.status = ActivityStatus.FAILED

    def reset(self) -> None:
        """
        Return the activity to PENDING so it re-runs on the next pass.

        The previous output is discarded here; the version it produced is
        retained on the deliverable, so nothing a reviewer saw is lost.
        """
        self.status = ActivityStatus.PENDING
        self.output = None
