from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from core.capabilities.capability_requirement import CapabilityRequirement


@dataclass
class Activity:
    """
    Represents a unit of work required to produce a deliverable.
    """

    id: UUID = field(default_factory=uuid4)
    name: str = ""
    description: str = ""
    required_capabilities: set[CapabilityRequirement] = field(default_factory=set)

    def requires(self, requirement: CapabilityRequirement) -> None:
        self.required_capabilities.add(requirement)

    def requires_all(
        self,
        requirements: set[CapabilityRequirement],
    ) -> None:
        self.required_capabilities.update(requirements)