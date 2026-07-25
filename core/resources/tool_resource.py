from dataclasses import dataclass, field

from core.capabilities.capability import Capability
from core.resources.resource import Resource


@dataclass
class ToolResource(Resource):
    """
    Represents a software tool capable of executing work.
    """

    tool_type: str = ""
    version: str | None = None
    capabilities: set[Capability] = field(default_factory=set)  # type: ignore[assignment]