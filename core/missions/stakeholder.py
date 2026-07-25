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