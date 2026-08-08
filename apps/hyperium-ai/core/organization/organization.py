from __future__ import annotations

from dataclasses import dataclass, field

from core.resources.resource import Resource


@dataclass
class Organization:
    """
    Represents the digital organization that executes missions.
    """

    name: str
    resources: list[Resource] = field(default_factory=list)

    def add_resource(self, resource: Resource) -> None:
        if resource not in self.resources:
            self.resources.append(resource)