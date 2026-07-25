from __future__ import annotations

from typing import List

from .constraint import Constraint
from .mission_validator import MissionValidator
from .objective import Objective
from .stakeholder import Stakeholder
from .success_criterion import SuccessCriterion


class Mission:
    """
    Represents the highest-level business objective within Hyperium.

    A Mission defines WHAT should be achieved.
    It intentionally does not define HOW it will be executed.
    """

    def __init__(
        self,
        title: str,
        objective: Objective,
    ) -> None:
        self.title = title
        self.objective = objective

        self.stakeholders: List[Stakeholder] = []
        self.constraints: List[Constraint] = []
        self.success_criteria: List[SuccessCriterion] = []

    def add_stakeholder(self, stakeholder: Stakeholder) -> None:
        self.stakeholders.append(stakeholder)

    def add_constraint(self, constraint: Constraint) -> None:
        self.constraints.append(constraint)

    def add_success_criterion(self, criterion: SuccessCriterion) -> None:
        self.success_criteria.append(criterion)

    def validate(self) -> None:
        MissionValidator.validate(self)