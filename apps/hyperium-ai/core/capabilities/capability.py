from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Capability:
    """
    Represents a business capability.

    Capabilities are immutable catalog items that can be provided
    by resources and required by activities.
    """

    name: str
    description: str = ""