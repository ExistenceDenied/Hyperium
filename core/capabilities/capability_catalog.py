from __future__ import annotations

from core.capabilities.capability import Capability


class CapabilityCatalog:
    """
    Central registry of business capabilities.
    """

    _capabilities: dict[str, Capability] = {
        "BUSINESS_ANALYSIS": Capability(
            name="Business Analysis",
            description="Analyse business needs and recommend solutions.",
        ),
        "REQUIREMENTS_ENGINEERING": Capability(
            name="Requirements Engineering",
            description="Elicit, document and validate requirements.",
        ),
        "RESEARCH": Capability(
            name="Research",
            description="Collect and synthesize information.",
        ),
        "ARCHITECTURE": Capability(
            name="Architecture",
            description="Design business and technical architectures.",
        ),
        "SOFTWARE_DEVELOPMENT": Capability(
            name="Software Development",
            description="Design and implement software solutions.",
        ),
        "TESTING": Capability(
            name="Testing",
            description="Verify and validate deliverables.",
        ),
        "TECHNICAL_WRITING": Capability(
            name="Technical Writing",
            description="Produce structured documentation.",
        ),
        "PRESENTATION_DESIGN": Capability(
            name="Presentation Design",
            description="Create presentation material.",
        ),
    }

    @classmethod
    def get(cls, key: str) -> Capability:
        return cls._capabilities[key]

    @classmethod
    def all(cls) -> tuple[Capability, ...]:
        return tuple(cls._capabilities.values())