from __future__ import annotations

from application.project.autonomous_runner import AutonomousRunner
from application.project.project_builder import ProjectBuilder
from application.review.quality_reviewer import QualityReviewer, ReviewVerdict
from core.interfaces.llm_provider import LLMProvider
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)

# ------------------------------------------------------- reviewer parsing


class _FixedLLM(LLMProvider):
    def __init__(self, response: str):
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response


def _deliverable():
    service = ProjectBuilder.build(
        ScriptedLLM(), InMemoryArtifactStore(), methodologies=FakeMethodologies()
    )
    project = service.start(build_mission(), resources=[build_consultant()])
    return project.mission, project.deliverable("requirements")


def test_reviewer_reads_an_approval():
    mission, deliverable = _deliverable()
    reviewer = QualityReviewer(_FixedLLM('{"approved": true, "feedback": "solid"}'))

    verdict = reviewer.review(mission, deliverable)

    assert verdict.approved is True
    assert verdict.feedback == "solid"


def test_reviewer_reads_a_rejection_with_feedback():
    mission, deliverable = _deliverable()
    reviewer = QualityReviewer(
        _FixedLLM('<think>hm</think>{"approved": false, "feedback": "too thin"}')
    )

    verdict = reviewer.review(mission, deliverable)

    assert verdict.approved is False
    assert verdict.feedback == "too thin"


def test_unparseable_review_is_a_rejection_not_a_crash():
    mission, deliverable = _deliverable()
    reviewer = QualityReviewer(_FixedLLM("I think it's fine, ship it."))

    verdict = reviewer.review(mission, deliverable)

    assert verdict.approved is False
    assert verdict.feedback  # a usable rework brief, not empty


# ------------------------------------------------ the autonomous loop


class StubReviewer:
    """Approves, or rejects a set number of times before approving."""

    def __init__(self, reject_times: int = 0):
        self._remaining = reject_times
        self.reviews = 0

    def review(self, mission, deliverable) -> ReviewVerdict:
        self.reviews += 1
        if self._remaining > 0:
            self._remaining -= 1
            return ReviewVerdict(False, "add more detail")
        return ReviewVerdict(True, "good")


def _autonomous(reviewer, max_revisions=2):
    service = ProjectBuilder.build(
        ScriptedLLM(), InMemoryArtifactStore(), methodologies=FakeMethodologies()
    )
    project = service.start(build_mission(), resources=[build_consultant()])
    return AutonomousRunner(service, reviewer, max_revisions=max_revisions).run(project)


def test_an_engagement_completes_when_every_deliverable_is_approved():
    outcome = _autonomous(StubReviewer())

    assert outcome.completed is True
    assert outcome.status == "COMPLETED"
    assert outcome.halted_on is None
    # Both deliverables (discovery + design) were approved.
    assert [d.decision for d in outcome.decisions] == ["approved", "approved"]


def test_a_rejection_causes_a_revision_then_completes():
    reviewer = StubReviewer(reject_times=1)

    outcome = _autonomous(reviewer)

    assert outcome.completed is True
    kinds = [d.decision for d in outcome.decisions]
    assert "revision 1" in kinds
    assert kinds.count("approved") >= 1


def test_it_halts_when_a_deliverable_never_passes():
    reviewer = StubReviewer(reject_times=99)

    outcome = _autonomous(reviewer, max_revisions=2)

    assert outcome.completed is False
    assert outcome.halted_on == "requirements"
    # Two revisions were requested, then it stopped.
    assert sum(1 for d in outcome.decisions if "revision" in d.decision) == 2
    assert outcome.decisions[-1].decision == "halted"
