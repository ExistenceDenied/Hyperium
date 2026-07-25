from __future__ import annotations

from dataclasses import dataclass, field

from core.resources.resource import Resource


@dataclass
class Team:
    """
    Represents a team within the organization.
    """

    name: str
    members: list[Resource] = field(default_factory=list)

    def add_member(self, resource: Resource) -> None:
        if resource not in self.members:
            self.members.append(resource)