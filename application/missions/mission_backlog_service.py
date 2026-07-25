from __future__ import annotations

import logging
from uuid import UUID

from core.missions.constraint import Constraint, ConstraintType
from core.missions.mission import Mission, MissionStateError
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from core.missions.objective import Objective
from core.missions.stakeholder import Stakeholder
from core.missions.success_criterion import SuccessCriterion
from core.project.project import Project
from core.resources.resource import Resource

logger = logging.getLogger(__name__)


class MissionBacklogService:
    """
    CRUD over the mission backlog, plus launching a mission into an
    engagement.

    A mission may be captured incomplete and refined over time; validation is
    enforced at launch, not at save. Once launched, the mission is frozen —
    the engagement holds its own snapshot, and letting the two drift apart
    would make the audit trail meaningless.
    """

    def __init__(self, repository, project_service=None) -> None:
        self._repository = repository
        self._project_service = project_service

    # ----------------------------------------------------------- create

    def create(
        self,
        title: str,
        objective: str,
        priority: MissionPriority = MissionPriority.MEDIUM,
        criteria: list[str] | None = None,
        constraints: list[tuple[str, str]] | None = None,
        stakeholders: list[tuple[str, str]] | None = None,
        methodology: str | None = None,
    ) -> Mission:
        if not title.strip():
            raise ValueError("Mission title is required.")

        if not objective.strip():
            raise ValueError("Mission objective is required.")

        mission = Mission(
            title=title.strip(),
            objective=Objective(description=objective.strip()),
            priority=priority,
            methodology=(methodology or "").strip().lower() or None,
        )

        for description in criteria or []:
            mission.add_success_criterion(
                SuccessCriterion(description=description)
            )

        for kind, description in constraints or []:
            mission.add_constraint(
                Constraint(
                    type=self._constraint_type(kind),
                    description=description,
                )
            )

        for name, role in stakeholders or []:
            mission.add_stakeholder(Stakeholder(name=name, role=role))

        self._repository.save(mission)
        logger.info("Mission '%s' added to the backlog (%s).", title, mission.id)

        return mission

    # ------------------------------------------------------------- read

    def get(self, mission_id: UUID) -> Mission:
        return self._repository.get(mission_id)

    def list(
        self,
        status: MissionStatus | None = None,
        include_archived: bool = False,
    ) -> list[Mission]:
        return self._repository.list(
            status=status,
            include_archived=include_archived,
        )

    # ----------------------------------------------------------- update

    def update(
        self,
        mission_id: UUID,
        title: str | None = None,
        objective: str | None = None,
        priority: MissionPriority | None = None,
        add_criteria: list[str] | None = None,
        clear_criteria: bool = False,
        add_constraints: list[tuple[str, str]] | None = None,
        clear_constraints: bool = False,
        add_stakeholders: list[tuple[str, str]] | None = None,
        clear_stakeholders: bool = False,
        methodology: str | None = None,
    ) -> Mission:
        mission = self._repository.get(mission_id)

        changes_content = any(
            [
                title is not None,
                objective is not None,
                add_criteria,
                clear_criteria,
                add_constraints,
                clear_constraints,
                add_stakeholders,
                clear_stakeholders,
            ]
        )

        if changes_content and not mission.is_editable:
            raise MissionStateError(
                f"Mission '{mission.title}' is {mission.status.value} and "
                f"cannot be edited. Restore it or create a new mission."
            )

        if title is not None:
            if not title.strip():
                raise ValueError("Mission title cannot be empty.")
            mission.title = title.strip()
            mission.touch()

        if objective is not None:
            if not objective.strip():
                raise ValueError("Mission objective cannot be empty.")
            mission.objective = Objective(description=objective.strip())
            mission.touch()

        if priority is not None:
            mission.priority = priority
            mission.touch()

        if methodology is not None:
            mission.methodology = methodology.strip().lower() or None
            mission.touch()

        if clear_criteria:
            mission.clear_success_criteria()

        for description in add_criteria or []:
            mission.add_success_criterion(
                SuccessCriterion(description=description)
            )

        if clear_constraints:
            mission.clear_constraints()

        for kind, description in add_constraints or []:
            mission.add_constraint(
                Constraint(
                    type=self._constraint_type(kind),
                    description=description,
                )
            )

        if clear_stakeholders:
            mission.clear_stakeholders()

        for name, role in add_stakeholders or []:
            mission.add_stakeholder(Stakeholder(name=name, role=role))

        self._repository.save(mission)

        return mission

    def mark_ready(self, mission_id: UUID) -> Mission:
        mission = self._repository.get(mission_id)
        mission.mark_ready()
        self._repository.save(mission)

        return mission

    def archive(self, mission_id: UUID) -> Mission:
        mission = self._repository.get(mission_id)
        mission.archive()
        self._repository.save(mission)

        return mission

    def restore(self, mission_id: UUID) -> Mission:
        mission = self._repository.get(mission_id)
        mission.restore()
        self._repository.save(mission)

        return mission

    # ----------------------------------------------------------- delete

    def delete(self, mission_id: UUID, force: bool = False) -> Mission:
        mission = self._repository.get(mission_id)

        if mission.is_launched and not force:
            raise MissionStateError(
                f"Mission '{mission.title}' has already been launched as "
                f"engagement {mission.project_id}. Deleting it orphans that "
                f"engagement. Pass force to delete anyway."
            )

        self._repository.delete(mission_id)
        logger.info("Mission '%s' deleted from the backlog.", mission.title)

        return mission

    # ----------------------------------------------------------- launch

    def launch(self, mission_id: UUID, resources: list[Resource]) -> Project:
        if self._project_service is None:
            raise RuntimeError(
                "This backlog service was built without a project service "
                "and cannot launch missions."
            )

        mission = self._repository.get(mission_id)

        if mission.is_launched:
            raise MissionStateError(
                f"Mission '{mission.title}' was already launched as "
                f"engagement {mission.project_id}."
            )

        if mission.status is MissionStatus.ARCHIVED:
            raise MissionStateError(
                f"Mission '{mission.title}' is archived. Restore it first."
            )

        mission.validate()

        project = self._project_service.start(mission, resources=resources)

        mission.mark_launched(project.id)
        self._repository.save(mission)

        logger.info(
            "Mission '%s' launched as engagement %s.",
            mission.title,
            project.id,
        )

        return project

    def _constraint_type(self, value: str) -> ConstraintType:
        try:
            return ConstraintType[value.strip().upper()]
        except KeyError:
            valid = ", ".join(item.name.lower() for item in ConstraintType)
            raise ValueError(
                f"Unknown constraint type '{value}'. Valid types: {valid}."
            ) from None
