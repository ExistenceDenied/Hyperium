"""
End-to-end coverage for Mission -> Analysis -> Methodology -> Plan -> Execution.

Since 2.0 the plan is authored by a methodology rather than by the model.
These tests pin that inversion: the same methodology always produces the same
work, and the model is confined to writing content.
"""

import pytest

from application.planning.planning_application_service import PlanningError
from application.project.project_builder import ProjectBuilder
from core.execution.deliverable_status import DeliverableStatus
from core.execution.execution_result import ExecutionStatus
from core.resources.ai_resource import AIResource
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


def build_service(llm, store, repository=None, methodologies=None):
    return ProjectBuilder.build(
        llm,
        store,
        repository=repository,
        methodologies=methodologies or FakeMethodologies(),
    )


def start(llm=None, store=None, resources=None, methodologies=None, mission=None):
    llm = llm or ScriptedLLM()
    store = store or InMemoryArtifactStore()
    resources = resources if resources is not None else [build_consultant()]

    project = build_service(llm, store, methodologies=methodologies).start(
        mission or build_mission(),
        resources=resources,
    )

    return project, llm, store


# --------------------------------------------------------------- planning


def test_the_methodology_authors_the_plan():
    project, _, _ = start()

    assert [d.key for d in project.deliverables] == ["requirements", "curriculum"]
    assert [a.key for a in project.execution_plan.activities] == [
        "elicit",
        "design-curriculum",
    ]


def test_planning_is_deterministic_across_runs():
    first, _, _ = start()
    second, _, _ = start()

    assert [a.key for a in first.execution_plan.activities] == [
        a.key for a in second.execution_plan.activities
    ]


def test_the_model_cannot_change_the_work():
    """The analysis is free-form; the plan is not."""
    rogue = ScriptedLLM(
        '{"summary": "s", "recommended_methodology": "test-two-stage",'
        ' "deliverables": [{"key": "invented", "name": "Invented"}]}'
    )

    project, _, _ = start(llm=rogue)

    assert [d.key for d in project.deliverables] == ["requirements", "curriculum"]


def test_deliverables_carry_their_stage():
    project, _, _ = start()

    assert project.deliverable("requirements").stage == "discovery"
    assert project.deliverable("curriculum").stage == "design"


def test_an_explicit_mission_methodology_wins():
    methodologies = FakeMethodologies([TWO_STAGE, SINGLE_STAGE])

    project, _, _ = start(
        methodologies=methodologies,
        mission=build_mission(methodology="test-single-stage"),
    )

    assert project.execution_plan.methodology_key == "test-single-stage"


def test_planning_fails_when_no_methodology_can_be_selected():
    blank = ScriptedLLM('{"summary": "s"}')

    with pytest.raises(PlanningError, match="does not invent them"):
        start(llm=blank)


def test_analysis_failure_does_not_stop_the_engagement():
    """Understanding is valuable but not load-bearing."""

    class Broken(ScriptedLLM):
        def generate(self, prompt):
            if "Engagement Analyst" in prompt:
                raise ConnectionError("model down")
            return super().generate(prompt)

    project, _, _ = start(
        llm=Broken(),
        mission=build_mission(methodology="test-two-stage"),
    )

    assert project.execution_result.status is ExecutionStatus.AWAITING_APPROVAL
    assert "Analysis unavailable" in project.analysis.rationale


def test_analysis_still_contributes_understanding():
    project, _, _ = start()

    assert "requirements baseline" in project.analysis.summary
    assert project.analysis.assumptions == ["Juniors have no prior BA training."]
    assert project.analysis.risks == ["One day may be too short."]


# ----------------------------------------------------------- stage gating


def test_the_first_stage_runs_and_stops_at_its_gate():
    project, _, _ = start()

    result = project.execution_result

    assert result.status is ExecutionStatus.AWAITING_APPROVAL
    assert result.activities_executed == 1
    assert [d.key for d in project.awaiting_approval] == ["requirements"]


def test_the_next_stage_is_blocked_until_the_gate_passes():
    project, _, _ = start()

    assert project.deliverable("curriculum").status is DeliverableStatus.DRAFT
    assert not project.execution_plan.activity_by_key(
        "design-curriculum"
    ).is_completed


def test_an_unmet_gate_is_reported_by_name():
    project, _, _ = start()

    assert any(
        "Quality gate 'discovery'" in message
        for message in project.execution_result.messages
    )


def test_approving_opens_the_gate_and_the_next_stage_runs():
    project, llm, store = start()

    project.approve("requirements", summary="Agreed.")
    resumed = build_service(llm, store).resume(project)

    assert resumed.execution_plan.gate_result("discovery").passed
    assert resumed.deliverable("curriculum").latest_version() is not None


def state_of(project, key):
    from core.methodologies.quality_gate import DeliverableState

    deliverable = project.deliverable(key)

    return DeliverableState(
        key=deliverable.key,
        approved=deliverable.is_approved,
        status=deliverable.status.value,
        content=deliverable.latest_version().content,
    )


def test_a_gate_can_require_a_minimum_length():
    from core.methodologies.quality_gate import QualityGate

    project, _, _ = start()
    gate = QualityGate(require_approval=False, minimum_words=10_000)

    result = gate.evaluate([state_of(project, "requirements")])

    assert not result.passed
    assert "requires at least 10000" in result.failures[0]


def test_a_gate_can_require_a_section():
    from core.methodologies.quality_gate import QualityGate

    project, _, _ = start()
    gate = QualityGate(require_approval=False, required_sections=("Budget",))

    result = gate.evaluate([state_of(project, "requirements")])

    assert not result.passed
    assert "missing the required section 'Budget'" in result.failures[0]


def test_dependencies_inside_one_deliverable_do_not_deadlock():
    project, _, _ = start(
        methodologies=FakeMethodologies([SINGLE_STAGE]),
        mission=build_mission(methodology="test-single-stage"),
    )

    assert project.execution_result.activities_executed == 2
    assert project.deliverable("requirements").latest_version() is not None


# ------------------------------------------------------------- techniques


def test_technique_guidance_reaches_the_prompt():
    _, llm, _ = start()

    activity_prompt = [p for p in llm.prompts if "Elicit learning needs" in p][0]

    assert "Technique: Stakeholder Interviewing" in activity_prompt
    assert "Ask open questions" in activity_prompt


def test_the_deliverable_structure_reaches_the_prompt():
    _, llm, _ = start()

    activity_prompt = [p for p in llm.prompts if "Elicit learning needs" in p][0]

    assert "expected to cover" in activity_prompt
    assert "Learning needs" in activity_prompt


def test_upstream_output_is_fed_into_the_downstream_prompt():
    project, llm, store = start()

    project.approve("requirements")
    build_service(llm, store).resume(project)

    downstream = [p for p in llm.prompts if "Design the curriculum" in p][0]

    assert "Work already completed" in downstream
    assert "Juniors must run an intake workshop." in downstream


# ---------------------------------------------------------------- content


def test_deliverable_content_is_generated_and_stored():
    project, _, store = start()

    version = project.deliverable("requirements").latest_version()

    assert version.version == 1
    assert version.filename == "requirements-v1.md"
    assert "Juniors must run an intake workshop." in version.content
    assert store.files["requirements-v1.md"] == version.content


# ----------------------------------------------------------------- rework


def test_rejecting_a_deliverable_regenerates_it():
    project, llm, store = start()

    project.request_changes("requirements", summary="Too thin, add detail.")
    reworked = build_service(llm, store).resume(project)

    assert [v.filename for v in reworked.deliverable("requirements").versions] == [
        "requirements-v1.md",
        "requirements-v2.md",
    ]


def test_reviewer_feedback_reaches_the_rework_prompt():
    project, llm, store = start()

    project.request_changes("requirements", summary="Add measurable outcomes.")
    build_service(llm, store).resume(project)

    assert "Add measurable outcomes." in llm.prompts[-1]


# ------------------------------------------------------------- allocation


def test_activity_with_no_capable_resource_blocks():
    project, _, _ = start(resources=[AIResource(name="Intern")])

    assert project.execution_result.status is ExecutionStatus.BLOCKED
    assert project.execution_result.activities_executed == 0


def test_human_allocated_work_is_reported_rather_than_faked():
    from core.capabilities.capability_catalog import CapabilityCatalog
    from core.capabilities.proficiency_level import ProficiencyLevel

    analyst = HumanResource(name="Priya", role="Business Analyst")
    analyst.add_capability(
        CapabilityCatalog.get("BUSINESS_ANALYSIS"),
        ProficiencyLevel.EXPERT,
    )

    project, _, _ = start(resources=[analyst])

    assert project.execution_result.status is ExecutionStatus.BLOCKED
    assert any(
        "awaits work outside Hyperium" in message
        for message in project.execution_result.messages
    )
