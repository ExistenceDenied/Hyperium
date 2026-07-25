from dataclasses import dataclass

from core.resources.resource import Resource


@dataclass
class AIResource(Resource):
    """
    Represents an AI model capable of executing work.
    """

    provider: str = ""
    model: str = ""