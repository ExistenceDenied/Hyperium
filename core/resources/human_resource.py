from dataclasses import dataclass, field

from core.capabilities.capability import Capability
from core.resources.resource import Resource


@dataclass
class HumanResource(Resource):
    """
    Represents a human capable of executing work.
    """

    role: str = ""
    capabilities: set[Capability] = field(default_factory=set)  # type: ignore[assignment]