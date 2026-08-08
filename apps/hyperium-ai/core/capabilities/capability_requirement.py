from __future__ import annotations

from dataclasses import dataclass

from core.capabilities.capability import Capability
from core.capabilities.proficiency_level import ProficiencyLevel


@dataclass(frozen=True, slots=True)
class CapabilityRequirement:
    """
    Represents a required capability and the expected proficiency.
    """

    capability: Capability
    minimum_level: ProficiencyLevel = ProficiencyLevel.BASIC
    mandatory: bool = True