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

    @property
    def executes_autonomously(self) -> bool:
        """
        Whether Hyperium runs this resource's work itself, or waits for the
        work to be submitted from outside.

        This is what separates a resource the engine can execute — today an AI
        model — from a human or an external tool, whose work arrives through
        `submit`. Answering it here, rather than by type-checking at each call
        site, is what lets a new autonomous resource type be added without
        editing the engine.
        """
        return False

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