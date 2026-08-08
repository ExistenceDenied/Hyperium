from dataclasses import dataclass

from core.resources.resource import Resource


@dataclass
class HumanResource(Resource):
    """
    Represents a human capable of executing work.
    """

    role: str = ""
