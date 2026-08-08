from __future__ import annotations

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

    @classmethod
    def match(cls, value: str) -> ConstraintType | None:
        """Return the type named by `value`, or None if it names none."""
        try:
            return cls[(value or "").strip().upper()]
        except KeyError:
            return None


@dataclass(frozen=True)
class Constraint:
    """
    Represents a constraint that limits or influences mission execution.
    """

    type: ConstraintType
    description: str
    mandatory: bool = True

    @classmethod
    def parse(cls, line: str) -> Constraint:
        """
        Read a constraint written as free text, with an optional type prefix.

        Both of these work::

            TIME: must ship in Q3
            Must ship in Q3

        A prefix that does not name a known type is **not** an error — it is
        part of the description. "COST: under budget" is an ordinary thing to
        write, and rejecting an entire mission because the category is spelled
        a way this enum does not recognise is hostile. Categories are for
        sorting, not for gatekeeping.
        """
        text = (line or "").strip()

        if not text:
            raise ValueError("A constraint cannot be empty.")

        prefix, separator, rest = text.partition(":")

        if separator and rest.strip():
            kind = ConstraintType.match(prefix)

            if kind is not None:
                return cls(type=kind, description=rest.strip())

        return cls(type=ConstraintType.OTHER, description=text)
