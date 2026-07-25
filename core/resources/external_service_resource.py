from dataclasses import dataclass, field

from core.capabilities.capability import Capability
from core.resources.resource import Resource


@dataclass
class ExternalServiceResource(Resource):
    """
    Represents an external service capable of executing work.
    """

    service_name: str = ""
    endpoint: str | None = None
    capabilities: set[Capability] = field(default_factory=set)  # type: ignore[assignment]