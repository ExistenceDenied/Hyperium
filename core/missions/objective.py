from dataclasses import dataclass
from typing import Optional


@dataclass
class Objective:
    """
    Represents the primary business objective of a mission.

    An objective describes *what* should be achieved,
    not *how* it will be achieved.
    """

    description: str
    rationale: Optional[str] = None
    business_value: Optional[str] = None