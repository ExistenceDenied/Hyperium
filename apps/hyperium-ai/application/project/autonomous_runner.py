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
        self._halted_on: str | None = None

        while True:
            awaiting = project.awaiting_approval

            if awaiting:
                self._review_awaiting(project, awaiting, revisions, decisions)
            else:
                # Nothing is waiting for approval. Either the engagement is
                # finished, or a deterministic gate is blocking on something an
                # approval cannot fix — a missing section, too few words. Send
                # the offending deliverable back to be regenerated against the
                # gate's own complaint. Without this the run deadlocks: the
                # reviewer approved the content, but the gate still refuses it.
                if not self._rework_blocked_gates(project, revisions, decisions):
                    break

            if self._halted_on is not None:
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
            halted_on=self._halted_on,
        )

    def _review_awaiting(self, project, awaiting, revisions, decisions) -> None:
        for deliverable in awaiting:
            key = deliverable.key
            verdict = self._reviewer.review(project.mission, deliverable)

            if verdict.approved:
                self._service.approve(
                    project, key, note=verdict.feedback or "Approved by the reviewer."
                )
                decisions.append(ReviewDecision(key, "approved", verdict.feedback))
                logger.info("Autonomous reviewer approved '%s'.", key)
                continue

            sent = self._send_back(
                project, key, verdict.feedback, revisions, decisions
            )
            if not sent:
                return

    def _rework_blocked_gates(self, project, revisions, decisions) -> bool:
        """
        Send back deliverables a quality gate is blocking on. Returns whether
        any progress was made — False means the engagement is done or stuck.
        """
        progressed = False

        for key, reason in self._gate_blocked(project):
            brief = (
                f"The quality gate is not yet satisfied: {reason} Revise the "
                "deliverable to address this specifically."
            )

            if not self._send_back(project, key, brief, revisions, decisions):
                return False

            progressed = True

        return progressed

    def _send_back(self, project, key, feedback, revisions, decisions) -> bool:
        """Request a revision, or record a halt if the cap is reached."""
        done = revisions.get(key, 0)

        if done >= self._max_revisions:
            decisions.append(ReviewDecision(key, "halted", feedback))
            logger.info("Halted on '%s' after %s revisions.", key, done)
            self._halted_on = key
            return False

        revisions[key] = done + 1
        self._service.request_changes(project, key, note=feedback)
        decisions.append(ReviewDecision(key, f"revision {done + 1}", feedback))
        logger.info("Sent '%s' back (revision %s).", key, done + 1)

        return True

    def _gate_blocked(self, project) -> list[tuple[str, str]]:
        plan = project.execution_plan

        if plan is None:
            return []

        blocked: list[tuple[str, str]] = []

        for stage_key, gate in plan.open_gates():
            for deliverable in plan.deliverables_in_stage(stage_key):
                if deliverable.latest_version() is None:
                    continue

                # Only failures this deliverable can fix by regenerating; an
                # approval failure is not one (it is already approved here).
                reasons = [
                    failure
                    for failure in gate.failures
                    if deliverable.key in failure
                    and "has not been approved" not in failure
                ]

                if reasons:
                    blocked.append((deliverable.key, " ".join(reasons)))

        return blocked
