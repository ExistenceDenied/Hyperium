from dataclasses import dataclass

from core.resources.resource import Resource


@dataclass
class ExternalServiceResource(Resource):
    """
    Represents an external service capable of executing work.
    """

    service_name: str = ""
    endpoint: str | None = None
