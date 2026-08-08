from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SuccessCriterion:
    """
    Represents a measurable criterion used to determine whether
    a mission has been successfully completed.
    """

    description: str
    metric: Optional[str] = None
    target: Optional[str] = None