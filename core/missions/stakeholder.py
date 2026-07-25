from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Stakeholder:
    """
    Represents a stakeholder involved in or impacted by a mission.
    """

    name: str
    role: str
    interest: Optional[str] = None
    influence: Optional[str] = None

    @classmethod
    def parse(cls, line: str) -> Stakeholder:
        """
        Read a stakeholder written as ``Name: role``.

        Unlike a constraint, both halves carry meaning and neither can be
        guessed from the other, so the separator is required.
        """
        name, separator, role = (line or "").partition(":")

        if not separator or not name.strip() or not role.strip():
            raise ValueError(
                f"Stakeholder '{line.strip()}' must be written as "
                f"'Name: role', for example 'Priya: Head of Operations'."
            )

        return cls(name=name.strip(), role=role.strip())
