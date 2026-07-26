from __future__ import annotations

import logging
from dataclasses import dataclass, field

from core.execution.execution_result import ExecutionStatus
from core.project.project import Project

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReviewDecision:
    """One decision the autonomous reviewer made, for the run report."""

    deliverable: str
    decision: str  # "approved", "revision N", or "halted"
    feedback: str


@dataclass
class AutonomousOutcome:
    project: Project
    decisions: list[ReviewDecision] = field(default_factory=list)
    status: str = ""
    completed: bool = False
    halted_on: str | None = None


class AutonomousRunner:
    """
    Drives an engagement to completion with no human in the loop.

    The engine produces a deliverable and stops at its approval gate, as
    always. Here an AI reviewer stands in for the person: it judges each
    deliverable and either approves it — advancing the engagement — or sends it
    back with feedback, which the engine regenerates against. That repeats,
    bounded by a per-deliverable revision cap, until the engagement completes or
    a deliverable cannot be made satisfactory. Nothing here touches the
    deterministic gate; approval and rework are the same acts a human performs.
    """

    def __init__(self, service, reviewer, max_revisions: int = 2) -> None:
        self._service = service
        self._reviewer = reviewer
        self._max_revisions = max_revisions

    def run(self, project: Project) -> AutonomousOutcome:
        revisions: dict[str, int] = {}
        decisions: list[ReviewDecision] = []
        halted_on: str | None = None

        while True:
            awaiting = project.awaiting_approval

            if not awaiting:
                break

            for deliverable in awaiting:
                key = deliverable.key
                verdict = self._reviewer.review(project.mission, deliverable)

                if verdict.approved:
                    self._service.approve(
                        project,
                        key,
                        note=verdict.feedback or "Approved by the reviewer.",
                    )
                    decisions.append(ReviewDecision(key, "approved", verdict.feedback))
                    logger.info("Autonomous reviewer approved '%s'.", key)
                    continue

                done = revisions.get(key, 0)

                if done >= self._max_revisions:
                    decisions.append(ReviewDecision(key, "halted", verdict.feedback))
                    logger.info(
                        "Autonomous reviewer halted on '%s' after %s revisions.",
                        key,
                        done,
                    )
                    halted_on = key
                    break

                revisions[key] = done + 1
                self._service.request_changes(project, key, note=verdict.feedback)
                decisions.append(
                    ReviewDecision(key, f"revision {done + 1}", verdict.feedback)
                )
                logger.info(
                    "Autonomous reviewer sent '%s' back (revision %s).",
                    key,
                    done + 1,
                )

            if halted_on is not None:
                break

            project = self._service.resume(project)

        result = project.execution_result
        status = result.status.value if result else "UNKNOWN"
        completed = bool(result and result.status is ExecutionStatus.COMPLETED)

        return AutonomousOutcome(
            project=project,
            decisions=decisions,
            status=status,
            completed=completed,
            halted_on=halted_on,
        )
