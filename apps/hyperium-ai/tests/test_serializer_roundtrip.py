"""
Serializer completeness.

`ProjectSerializer` is a hand-written mirror of the domain model. Nothing
stopped a newly added field from being silently absent from persistence — an
engagement would round-trip looking correct and quietly lose data.

These tests reflect over the dataclasses, so adding a field to the domain
fails here until it is mapped.
"""

from __future__ import annotations

import dataclasses

import pytest

from application.project.project_builder import ProjectBuilder
from core.execution.activity import Activity
from core.execution.deliverable import Deliverable
from core.execution.deliverable_version import DeliverableVersion
from core.execution.execution_plan import ExecutionPlan
from core.execution.execution_result import ExecutionResult
from core.execution.stage_plan import StagePlan
from core.missions.constraint import Constraint, ConstraintType
from core.missions.stakeholder import Stakeholder
from core.missions.success_criterion import SuccessCriterion
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.project_serializer import ProjectSerializer
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


def populated_project():
    """An engagement exercised far enough to touch every branch."""
    project = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        methodologies=FakeMethodologies(),
    ).start(build_mission(), resources=[build_consultant()])

    project.mission.add_constraint(
        Constraint(type=ConstraintType.TIME, description="Ship in Q3")
    )
    project.mission.add_stakeholder(Stakeholder(name="Priya", role="Sponsor"))
    project.mission.add_success_criterion(
        SuccessCriterion(description="Adopted", metric="uptake", target="80%")
    )
    project.approve("requirements", summary="Approved with a note.")

    return project


def round_trip(project):
    serializer = ProjectSerializer()

    return serializer.from_dict(serializer.to_dict(project))


# ------------------------------------------------------- field coverage


def persisted_keys(payload, path):
    node = payload
    for step in path:
        node = node[step] if not isinstance(step, int) else node[step]
    return set(node)


@pytest.mark.parametrize(
    "cls, path, ignore",
    [
        (Activity, ("execution_plan", "deliverables", 0, "activities", 0), {"id"}),
        (Deliverable, ("execution_plan", "deliverables", 0), set()),
        (
            DeliverableVersion,
            ("execution_plan", "deliverables", 0, "versions", 0),
            set(),
        ),
        (StagePlan, ("execution_plan", "stages", 0), set()),
        (ExecutionResult, ("execution_result",), set()),
    ],
)
def test_every_domain_field_is_persisted(cls, path, ignore):
    """
    Reflects over the dataclass: a new field fails this test until the
    serializer maps it.
    """
    payload = ProjectSerializer().to_dict(populated_project())

    node = payload
    for step in path:
        node = node[step]

    declared = {field.name for field in dataclasses.fields(cls)} - ignore
    missing = declared - set(node)

    assert not missing, (
        f"{cls.__name__} fields are not persisted: {sorted(missing)}. "
        f"Add them to ProjectSerializer and bump SCHEMA_VERSION."
    )


def test_execution_plan_fields_are_persisted():
    payload = ProjectSerializer().to_dict(populated_project())
    node = payload["execution_plan"]

    declared = {field.name for field in dataclasses.fields(ExecutionPlan)}
    # allocations and activities are persisted under their own shapes
    covered = set(node) | {"allocations", "activities"}

    assert not declared - covered, sorted(declared - covered)


# ------------------------------------------------------ value round-trip


def test_the_whole_engagement_survives_a_round_trip():
    original = populated_project()
    restored = round_trip(original)

    assert restored.id == original.id
    assert restored.mission.title == original.mission.title
    assert restored.mission.methodology == original.mission.methodology
    assert [c.description for c in restored.mission.constraints] == [
        c.description for c in original.mission.constraints
    ]
    assert restored.mission.constraints[0].type is ConstraintType.TIME
    assert [s.name for s in restored.mission.stakeholders] == ["Priya"]
    assert restored.mission.success_criteria[-1].target == "80%"


def test_the_analysis_survives():
    original = populated_project()
    restored = round_trip(original)

    assert restored.analysis.summary == original.analysis.summary
    assert restored.analysis.assumptions == original.analysis.assumptions
    assert restored.analysis.risks == original.analysis.risks
    assert (
        restored.analysis.recommended_methodology
        == original.analysis.recommended_methodology
    )


def test_activities_survive_with_status_output_and_technique():
    original = populated_project()
    restored = round_trip(original)

    for before in original.execution_plan.activities:
        after = restored.execution_plan.activity_by_key(before.key)

        assert after is not None
        assert after.status is before.status
        assert after.output == before.output
        assert after.technique == before.technique
        assert after.depends_on == before.depends_on
        assert {r.capability.name for r in after.required_capabilities} == {
            r.capability.name for r in before.required_capabilities
        }


def test_versions_and_review_notes_survive():
    original = populated_project()
    restored = round_trip(original)

    before = original.deliverable("requirements").latest_version()
    after = restored.deliverable("requirements").latest_version()

    assert after.version == before.version
    assert after.content == before.content
    assert after.filename == before.filename
    assert after.review_summary == "Approved with a note."
    assert after.created_at == before.created_at


def test_stages_and_gates_survive():
    original = populated_project()
    restored = round_trip(original)

    for before in original.execution_plan.stages:
        after = restored.execution_plan.stage(before.key)

        assert after is not None
        assert after.name == before.name
        assert after.depends_on == before.depends_on
        assert (after.quality_gate is None) == (before.quality_gate is None)

        if before.quality_gate:
            assert after.quality_gate == before.quality_gate


def test_allocations_survive():
    original = populated_project()
    restored = round_trip(original)

    for before in original.execution_plan.activities:
        after = restored.execution_plan.activity_by_key(before.key)

        expected = original.execution_plan.get_resource(before)
        actual = restored.execution_plan.get_resource(after)

        assert (expected is None) == (actual is None)

        if expected is not None:
            assert actual.name == expected.name
            assert set(actual.capabilities) == set(expected.capabilities)


def test_gate_evaluation_is_identical_after_a_round_trip():
    """The strongest check: governance behaves the same on a resumed plan."""
    original = populated_project()
    restored = round_trip(original)

    for stage in original.execution_plan.stages:
        before = original.execution_plan.gate_result(stage.key)
        after = restored.execution_plan.gate_result(stage.key)

        assert after.passed == before.passed
        assert after.failures == before.failures
