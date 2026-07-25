from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .mission import Mission


class MissionValidationError(ValueError):
    """Raised when a Mission is invalid."""


class MissionValidator:
    """
    Validates the business rules of a Mission.
    """

    @staticmethod
    def validate(mission: "Mission") -> None:
        if not mission.title.strip():
            raise MissionValidationError("Mission title is required.")

        if not mission.objective.description.strip():
            raise MissionValidationError("Mission objective is required.")

        if not mission.success_criteria:
            raise MissionValidationError(
                "A mission must define at least one success criterion."
            )