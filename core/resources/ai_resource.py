from dataclasses import dataclass, field

from core.capabilities.capability import Capability
from core.resources.resource import Resource


@dataclass
class AIResource(Resource):
    """
    Represents an AI model capable of executing work.
    """

    provider: str = ""
    model: str = ""
    capabilities: set[Capability] = field(default_factory=set)  # type: ignore[assignment]