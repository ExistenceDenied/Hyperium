from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from core.capabilities.capability import Capability
from core.capabilities.proficiency_level import ProficiencyLevel


@dataclass
class Resource(ABC):
    """
    Base class for any resource capable of executing work.
    """

    name: str
    capabilities: dict[Capability, ProficiencyLevel] = field(default_factory=dict)

    def has_capability(self, capability: Capability) -> bool:
        return capability in self.capabilities

    def proficiency(
        self,
        capability: Capability,
    ) -> ProficiencyLevel | None:
        return self.capabilities.get(capability)

    def add_capability(
        self,
        capability: Capability,
        level: ProficiencyLevel,
    ) -> None:
        self.capabilities[capability] = level

    def remove_capability(
        self,
        capability: Capability,
    ) -> None:
        self.capabilities.pop(capability, None)