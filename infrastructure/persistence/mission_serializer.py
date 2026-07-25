from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from core.missions.constraint import Constraint, ConstraintType
from core.missions.mission import Mission
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from core.missions.objective import Objective
from core.missions.stakeholder import Stakeholder
from core.missions.success_criterion import SuccessCriterion

SCHEMA_VERSION = 1


class MissionSerializer:
    """
    Converts a Mission to and from plain dictionaries.

    Shared by the backlog repository and by ProjectSerializer, so a mission
    has exactly one persisted shape wherever it appears.
    """

    def to_dict(self, mission: Mission) -> dict[str, Any]:
        return {
            "id": str(mission.id),
            "title": mission.title,
            "status": mission.status.value,
            "priority": mission.priority.name,
            "created_at": mission.created_at.isoformat(),
            "updated_at": mission.updated_at.isoformat(),
            "project_id": (
                str(mission.project_id) if mission.project_id else None
            ),
            "methodology": mission.methodology,
            "objective": {
                "description": mission.objective.description,
                "rationale": mission.objective.rationale,
                "business_value": mission.objective.business_value,
            },
            "success_criteria": [
                {
                    "description": item.description,
                    "metric": item.metric,
                    "target": item.target,
                }
                for item in mission.success_criteria
            ],
            "constraints": [
                {
                    "type": item.type.name,
                    "description": item.description,
                    "mandatory": item.mandatory,
                }
                for item in mission.constraints
            ],
            "stakeholders": [
                {
                    "name": item.name,
                    "role": item.role,
                    "interest": item.interest,
                    "influence": item.influence,
                }
                for item in mission.stakeholders
            ],
        }

    def from_dict(self, payload: dict[str, Any]) -> Mission:
        mission = Mission(
            title=payload["title"],
            objective=Objective(**payload["objective"]),
            id=UUID(payload["id"]) if payload.get("id") else None,
            status=MissionStatus(payload.get("status", "DRAFT")),
            priority=MissionPriority[payload.get("priority", "MEDIUM")],
            created_at=self._time(payload.get("created_at")),
            updated_at=self._time(payload.get("updated_at")),
            project_id=(
                UUID(payload["project_id"])
                if payload.get("project_id")
                else None
            ),
            methodology=payload.get("methodology"),
        )

        for entry in payload.get("success_criteria", []):
            mission.success_criteria.append(SuccessCriterion(**entry))

        for entry in payload.get("constraints", []):
            mission.constraints.append(
                Constraint(
                    type=ConstraintType[entry.get("type", "OTHER")],
                    description=entry["description"],
                    mandatory=entry.get("mandatory", True),
                )
            )

        for entry in payload.get("stakeholders", []):
            mission.stakeholders.append(Stakeholder(**entry))

        # Restore the recorded timestamp; appending above would bump it.
        mission.updated_at = self._time(payload.get("updated_at")) or (
            mission.updated_at
        )

        return mission

    def _time(self, value: Any) -> datetime | None:
        if not value:
            return None

        return datetime.fromisoformat(value)
