from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4

from .constraint import Constraint
from .mission_priority import MissionPriority
from .mission_status import MissionStatus
from .mission_validator import MissionValidator
from .objective import Objective
from .stakeholder import Stakeholder
from .success_criterion import SuccessCriterion


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MissionStateError(RuntimeError):
    """
    Raised when an operation is not allowed in the mission's current state.
    """


class Mission:
    """
    Represents the highest-level business objective within Hyperium.

    A Mission defines WHAT should be achieved.
    It intentionally does not define HOW it will be executed.

    Missions live in a backlog independently of execution. They carry their
    own identity and lifecycle so an idea can be captured, refined and
    prioritised long before an engagement runs.
    """

    def __init__(
        self,
        title: str,
        objective: Objective,
        id: Optional[UUID] = None,
        status: MissionStatus = MissionStatus.DRAFT,
        priority: MissionPriority = MissionPriority.MEDIUM,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        project_id: Optional[UUID] = None,
        methodology: Optional[str] = None,
    ) -> None:
        self.id = id or uuid4()
        self.title = title
        self.objective = objective
        self.status = status
        self.priority = priority
        # An explicit choice overrides whatever the analysis recommends.
        self.methodology = methodology
        self.created_at = created_at or _now()
        self.updated_at = updated_at or self.created_at
        self.project_id = project_id

        self.stakeholders: List[Stakeholder] = []
        self.constraints: List[Constraint] = []
        self.success_criteria: List[SuccessCriterion] = []

    # ------------------------------------------------------------ content

    def add_stakeholder(self, stakeholder: Stakeholder) -> None:
        self.stakeholders.append(stakeholder)
        self.touch()

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)
        self.touch()

    def add_success_criterion(self, criterion: SuccessCriterion) -> None:
        self.success_criteria.append(criterion)
        self.touch()

    def clear_success_criteria(self) -> None:
        self.success_criteria.clear()
        self.touch()

    def clear_constraints(self) -> None:
        self.constraints.clear()
        self.touch()

    # ---------------------------------------------------------- lifecycle

    def touch(self) -> None:
        self.updated_at = _now()

    @property
    def is_launched(self) -> bool:
        return self.status is MissionStatus.LAUNCHED

    @property
    def is_editable(self) -> bool:
        """
        A launched mission is frozen. The engagement holds its own snapshot,
        so editing the backlog entry afterwards would silently desynchronise
        the two.
        """
        return self.status in (MissionStatus.DRAFT, MissionStatus.READY)

    @property
    def is_complete(self) -> bool:
        """Whether the mission would pass validation, without raising."""
        try:
            self.validate()
        except Exception:
            return False

        return True

    def mark_ready(self) -> None:
        self.validate()
        self.status = MissionStatus.READY
        self.touch()

    def mark_launched(self, project_id: UUID) -> None:
        self.status = MissionStatus.LAUNCHED
        self.project_id = project_id
        self.touch()

    def archive(self) -> None:
        if self.is_launched:
            raise MissionStateError(
                "A launched mission cannot be archived; archive the "
                "engagement instead."
            )

        self.status = MissionStatus.ARCHIVED
        self.touch()

    def restore(self) -> None:
        if self.status is not MissionStatus.ARCHIVED:
            raise MissionStateError("Only an archived mission can be restored.")

        self.status = MissionStatus.DRAFT
        self.touch()

    def validate(self) -> None:
        MissionValidator.validate(self)
