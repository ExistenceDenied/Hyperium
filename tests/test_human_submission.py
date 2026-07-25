"""
Humans submitting work assigned to them.

This closes the last functional gap in 1.0: HumanResource was modelled and
allocated, but a person had no way to hand their output back, so any plan
mixing human and AI capabilities ended BLOCKED forever.
"""

import pytest

from application.project.project_builder import ProjectBuilder
from core.capabilities.capability_catalog import CapabilityCatalog
from core.capabilities.proficiency_level import ProficiencyLevel
from core.execution.execution_result import ExecutionStatus
from core.resources.human_resource import HumanResource
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from tests.fixtures import (
    SINGLE_STAGE,
    TWO_STAGE,
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


def analyst() -> HumanResource:
    person = HumanResource(name="Priya", role="Business Analyst")

    for key in CapabilityCatalog.keys():
        person.add_capability(
            CapabilityCatalog.get(key),
            ProficiencyLevel.EXPERT,
        )

    return person


def start(resources, methodology=SINGLE_STAGE):
    llm = ScriptedLLM()
    store = InMemoryArtifactStore()
    service = ProjectBuilder.build(
        llm,
        store,
        methodologies=FakeMethodologies([methodology]),
    )
    mission = build_mission(methodology=methodology.key)

    return service.start(mission, resources=resources), service, store


def test_a_human_activity_blocks_until_work_is_submitted():
    project, _, _ = start([analyst()])

    assert project.execution_result.status is ExecutionStatus.BLOCKED
    assert project.execution_result.activities_executed == 0


def test_submitting_work_completes_the_activity_and_continues():
    project, service, store = start([analyst()])

    updated = service.submit_work(
        project,
        "elicit",
        "## Learning needs\nGathered in a workshop on Tuesday.",
    )

    elicit = updated.execution_plan.activity_by_key("elicit")

    assert elicit.is_completed
    assert "workshop on Tuesday" in elicit.output


def test_submitted_work_reaches_the_deliverable():
    project, service, store = start([analyst()])

    service.submit_work(project, "elicit", "## Needs\nFrom the workshop.")
    updated = service.submit_work(project, "document", "## Spec\nWritten up.")

    version = updated.deliverable("requirements").latest_version()

    assert version is not None
    assert "From the workshop." in version.content
    assert "Written up." in version.content
    assert updated.execution_result.status is ExecutionStatus.AWAITING_APPROVAL


def test_a_mixed_human_and_ai_plan_completes():
    """
    The AI does what it can, the human fills the rest, and the deliverable
    is produced from both.
    """
    person = HumanResource(name="Priya", role="Business Analyst")
    person.add_capability(
        CapabilityCatalog.get("BUSINESS_ANALYSIS"),
        ProficiencyLevel.EXPERT,
    )

    ai = build_consultant()
    ai.capabilities.pop(CapabilityCatalog.get("BUSINESS_ANALYSIS"), None)

    project, service, _ = start([person, ai])

    # The AI-allocated activity depends on the human one, so nothing ran yet.
    assert project.execution_result.activities_executed == 0

    updated = service.submit_work(project, "elicit", "## Needs\nFrom interviews.")

    assert updated.execution_result.status is ExecutionStatus.AWAITING_APPROVAL
    assert updated.execution_plan.activity_by_key("document").is_completed


def test_submitting_for_an_ai_activity_is_refused():
    """
    Uses the two-stage methodology, where the downstream activity is still
    pending behind the quality gate and allocated to the AI.
    """
    project, service, _ = start([build_consultant()], methodology=TWO_STAGE)

    with pytest.raises(ValueError, match="executed by Hyperium"):
        service.submit_work(project, "design-curriculum", "I did it myself.")


def test_submitting_twice_is_refused():
    project, service, _ = start([analyst()])

    service.submit_work(project, "elicit", "## Needs\nDone.")

    with pytest.raises(ValueError, match="already been completed"):
        service.submit_work(project, "elicit", "Again.")


def test_submitting_out_of_order_is_refused():
    project, service, _ = start([analyst()])

    with pytest.raises(ValueError, match="not ready"):
        service.submit_work(project, "document", "Skipping ahead.")


def test_submitting_empty_work_is_refused():
    project, service, _ = start([analyst()])

    with pytest.raises(ValueError, match="cannot be empty"):
        service.submit_work(project, "elicit", "   ")


def test_submitting_for_an_unknown_activity_lists_the_valid_keys():
    project, service, _ = start([analyst()])

    with pytest.raises(ValueError, match="Known: elicit, document"):
        service.submit_work(project, "nope", "Work.")
