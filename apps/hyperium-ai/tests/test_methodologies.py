"""
Methodology model, validation, loading and deterministic planning.

Authoring errors must surface once, at load time, by name — not halfway
through an engagement.
"""

import json

import pytest

from core.methodologies.methodology import (
    ActivityTemplate,
    DeliverableTemplate,
    Methodology,
    MethodologyError,
    Stage,
)
from core.methodologies.quality_gate import QualityGate
from core.planning.methodology_planner import MethodologyPlanner
from infrastructure.methodologies.json_methodology_repository import (
    JsonMethodologyRepository,
    MethodologyNotFoundError,
)
from tests.fixtures import TWO_STAGE, build_mission


def activity(key, *depends_on, capabilities=("BUSINESS_ANALYSIS",)):
    return ActivityTemplate(
        key=key,
        name=key,
        capabilities=capabilities,
        depends_on=tuple(depends_on),
    )


def deliverable(key, *activities):
    return DeliverableTemplate(key=key, name=key, activities=tuple(activities))


def stage(key, *deliverables, depends_on=()):
    return Stage(
        key=key,
        name=key,
        depends_on=tuple(depends_on),
        deliverables=tuple(deliverables),
    )


def methodology(*stages):
    return Methodology(key="m", name="M", stages=tuple(stages))


# ------------------------------------------------------------- validation


def test_a_well_formed_methodology_validates():
    methodology(stage("s", deliverable("d", activity("a")))).validate()


def test_rejects_a_methodology_with_no_stages():
    with pytest.raises(MethodologyError, match="no stages"):
        methodology().validate()


def test_rejects_a_stage_with_no_deliverables():
    with pytest.raises(MethodologyError, match="no deliverables"):
        methodology(stage("s")).validate()


def test_rejects_a_deliverable_with_no_activities():
    with pytest.raises(MethodologyError, match="no activities"):
        methodology(stage("s", deliverable("d"))).validate()


def test_rejects_an_activity_with_no_capabilities():
    bad = ActivityTemplate(key="a", name="a", capabilities=())

    with pytest.raises(MethodologyError, match="could never be allocated"):
        methodology(stage("s", deliverable("d", bad))).validate()


def test_rejects_duplicate_activity_keys():
    with pytest.raises(MethodologyError, match="Duplicate activity"):
        methodology(
            stage("s", deliverable("d", activity("a"), activity("a")))
        ).validate()


def test_rejects_an_unknown_activity_dependency():
    with pytest.raises(MethodologyError, match="unknown activity 'ghost'"):
        methodology(stage("s", deliverable("d", activity("a", "ghost")))).validate()


def test_rejects_a_self_dependent_activity():
    with pytest.raises(MethodologyError, match="depends on itself"):
        methodology(stage("s", deliverable("d", activity("a", "a")))).validate()


def test_rejects_an_unknown_stage_dependency():
    with pytest.raises(MethodologyError, match="unknown stage"):
        methodology(
            stage("s", deliverable("d", activity("a")), depends_on=("ghost",))
        ).validate()


def test_rejects_circular_stages():
    first = stage("one", deliverable("d1", activity("a1")), depends_on=("two",))
    second = stage("two", deliverable("d2", activity("a2")), depends_on=("one",))

    with pytest.raises(MethodologyError, match="circular"):
        methodology(first, second).validate()


def test_rejects_a_dependency_on_a_later_stage():
    """A backwards edge would make the stage sequence a lie."""
    first = stage("one", deliverable("d1", activity("a1", "a2")))
    second = stage("two", deliverable("d2", activity("a2")), depends_on=("one",))

    with pytest.raises(MethodologyError, match="belongs to a later stage"):
        methodology(first, second).validate()


# ---------------------------------------------------------- quality gates


def test_a_gate_with_no_deliverables_fails():
    result = QualityGate().evaluate([])

    assert not result.passed
    assert "produced no deliverables" in result.failures[0]


def test_a_gate_result_is_falsy_when_it_fails():
    assert not QualityGate().evaluate([])
    assert QualityGate(require_approval=False).evaluate([]) is not None


# ------------------------------------------------------------- json loading


def write(root, name, payload, subdir=None):
    directory = root / subdir if subdir else root
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(json.dumps(payload), encoding="utf-8")


MINIMAL = {
    "key": "demo",
    "name": "Demo",
    "stages": [
        {
            "key": "s",
            "name": "S",
            "deliverables": [
                {
                    "key": "d",
                    "name": "D",
                    "sections": ["One"],
                    "activities": [
                        {
                            "key": "a",
                            "name": "A",
                            "capabilities": ["BUSINESS_ANALYSIS"],
                        }
                    ],
                }
            ],
        }
    ],
}


def test_loads_a_methodology_from_disk(tmp_path):
    write(tmp_path, "demo.json", MINIMAL)

    repository = JsonMethodologyRepository([tmp_path])

    assert repository.keys() == ["demo"]
    assert repository.get("demo").name == "Demo"
    assert repository.get("DEMO ").key == "demo"


def test_an_unknown_key_lists_what_is_available(tmp_path):
    write(tmp_path, "demo.json", MINIMAL)

    with pytest.raises(MethodologyNotFoundError, match="Available: demo"):
        JsonMethodologyRepository([tmp_path]).get("nope")


def test_an_invalid_methodology_fails_at_load_naming_the_file(tmp_path):
    broken = {**MINIMAL, "stages": []}
    write(tmp_path, "broken.json", broken)

    with pytest.raises(MethodologyError, match="broken.json"):
        JsonMethodologyRepository([tmp_path]).all()


def test_malformed_json_fails_by_name(tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")

    with pytest.raises(MethodologyError, match="not valid JSON"):
        JsonMethodologyRepository([tmp_path]).all()


def test_an_unknown_technique_reference_is_rejected(tmp_path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["stages"][0]["deliverables"][0]["activities"][0]["technique"] = "ghost"
    write(tmp_path, "demo.json", payload)

    with pytest.raises(MethodologyError, match="unknown technique 'ghost'"):
        JsonMethodologyRepository([tmp_path]).all()


def test_techniques_load_and_resolve(tmp_path):
    payload = json.loads(json.dumps(MINIMAL))
    payload["stages"][0]["deliverables"][0]["activities"][0]["technique"] = "mapping"
    write(tmp_path, "demo.json", payload)
    write(
        tmp_path,
        "mapping.json",
        {
            "key": "mapping",
            "name": "Mapping",
            "guidance": "Draw the map.",
            "capabilities": ["BUSINESS_ANALYSIS"],
        },
        subdir="techniques",
    )

    repository = JsonMethodologyRepository([tmp_path])

    assert repository.technique("mapping").guidance == "Draw the map."
    assert repository.technique("nope") is None


# ---------------------------------------------- the shipped methodologies


def test_every_shipped_methodology_is_valid():
    repository = JsonMethodologyRepository()

    methodologies = repository.all()

    assert len(methodologies) >= 3

    for item in methodologies:
        item.validate()


def test_every_shipped_activity_uses_a_real_capability():
    from core.capabilities.capability_catalog import CapabilityCatalog

    valid = set(CapabilityCatalog.keys())

    for item in JsonMethodologyRepository().all():
        for activity_template in item.activities:
            assert set(activity_template.capabilities) <= valid


# ------------------------------------------------------ deterministic plan


def test_the_planner_reproduces_the_methodology_exactly():
    deliverables = MethodologyPlanner().build(TWO_STAGE, build_mission())

    assert [d.key for d in deliverables] == ["requirements", "curriculum"]
    assert deliverables[0].stage == "discovery"
    assert deliverables[0].sections == ("Learning needs", "Constraints")
    assert deliverables[0].activities[0].technique == "interviewing"


def test_stage_order_becomes_activity_dependencies():
    deliverables = MethodologyPlanner().build(TWO_STAGE, build_mission())

    downstream = deliverables[1].activities[0]

    assert "elicit" in downstream.depends_on


def test_planning_the_same_methodology_twice_gives_the_same_shape():
    first = MethodologyPlanner().build(TWO_STAGE, build_mission())
    second = MethodologyPlanner().build(TWO_STAGE, build_mission())

    assert [d.key for d in first] == [d.key for d in second]
    assert [a.key for d in first for a in d.activities] == [
        a.key for d in second for a in d.activities
    ]


def test_the_planner_rejects_an_invalid_methodology():
    with pytest.raises(MethodologyError):
        MethodologyPlanner().build(methodology(), build_mission())


def test_every_shipped_methodology_produces_an_orderable_plan():
    """The real proof: each shipped methodology can actually be executed."""
    from core.planning.dependency_graph import topological_order

    for item in JsonMethodologyRepository().all():
        deliverables = MethodologyPlanner().build(item, build_mission())
        activities = [a for d in deliverables for a in d.activities]

        ordered = topological_order(activities)

        assert len(ordered) == len(activities)


# ------------------------------------------- stage as the review boundary


def test_deliverables_in_one_stage_do_not_gate_each_other():
    """
    Regression from a live run: a stage stalled half-finished because one
    deliverable depended on another in the SAME stage, and the cross-
    deliverable approval rule demanded a sign-off that could not happen —
    the stage gate needs every deliverable complete before it can pass.
    """
    from application.project.project_builder import ProjectBuilder
    from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
    from tests.fixtures import FakeMethodologies, ScriptedLLM, build_consultant

    cross = Methodology(
        key="cross",
        name="Cross",
        stages=(
            Stage(
                key="discovery",
                name="Discovery",
                quality_gate=QualityGate(require_approval=True),
                deliverables=(
                    deliverable("first", activity("a")),
                    # depends on work in a sibling deliverable, same stage
                    deliverable("second", activity("b", "a")),
                ),
            ),
        ),
    )

    project = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        methodologies=FakeMethodologies([cross]),
    ).start(
        build_mission(methodology="cross"),
        resources=[build_consultant()],
    )

    assert project.execution_result.activities_executed == 2
    assert project.deliverable("first").latest_version() is not None
    assert project.deliverable("second").latest_version() is not None


def test_every_shipped_methodology_can_complete_its_first_stage():
    """
    The live-run check, offline: no shipped methodology may strand a stage.
    """
    from application.project.project_builder import ProjectBuilder
    from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
    from tests.fixtures import FakeMethodologies, ScriptedLLM, build_consultant

    for item in JsonMethodologyRepository().all():
        project = ProjectBuilder.build(
            ScriptedLLM(),
            InMemoryArtifactStore(),
            methodologies=FakeMethodologies([item]),
        ).start(
            build_mission(methodology=item.key),
            resources=[build_consultant()],
        )

        first = item.stages[0]
        produced = [
            project.deliverable(d.key).latest_version() is not None
            for d in first.deliverables
        ]

        assert all(produced), (
            f"{item.key}: stage '{first.key}' stranded — "
            f"{produced.count(False)} deliverable(s) never completed"
        )
