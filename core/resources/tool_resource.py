from dataclasses import dataclass

from core.resources.resource import Resource


@dataclass
class ToolResource(Resource):
    """
    Represents a software tool capable of executing work.
    """

    tool_type: str = ""
    version: str | None = None
