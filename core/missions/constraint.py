from dataclasses import dataclass
from enum import Enum


class ConstraintType(Enum):
    """
    Defines the category of a mission constraint.
    """

    BUSINESS = "Business"
    TECHNICAL = "Technical"
    LEGAL = "Legal"
    REGULATORY = "Regulatory"
    FINANCIAL = "Financial"
    RESOURCE = "Resource"
    TIME = "Time"
    QUALITY = "Quality"
    OTHER = "Other"


@dataclass(frozen=True)
class Constraint:
    """
    Represents a constraint that limits or influences mission execution.
    """

    type: ConstraintType
    description: str
    mandatory: bool = True