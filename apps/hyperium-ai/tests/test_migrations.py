"""
Schema migrations.

Each hop is tested against a payload in the shape that version genuinely
produced, and the whole chain is tested from version 1 through to current.
The point is not that migration succeeds — it is that an engagement saved a
year ago still opens, and that nothing is quietly invented on the way.
"""

from __future__ import annotations

import json

import pytest

from infrastructure.persistence.migrations import SchemaError, upgrade
from infrastructure.persistence.project_repository import ProjectRepository
from infrastructure.persistence.project_serializer import (
    SCHEMA_VERSION,
    ProjectSerializer,
)

PROJECT_ID = "11111111-2222-3333-4444-555555555555"


def v1_payload() -> dict:
    """The shape before missions had identity."""
    return {
        "schema_version": 1,
        "id": PROJECT_ID,
        "mission": {
            "title": "Reduce onboarding time",
            "objective": {
                "description": "Halve time-to-first-value.",
                "rationale": None,
                "business_value": None,
            },
            "success_criteria": [{"description": "Active in 14 days."}],
            "constraints": [{"description": "Must ship in Q3"}],
        },
        "analysis": {
            "summary": "A discovery engagement.",
            "assumptions": ["Data is available."],
            "risks": ["Scope creep."],
            "deliverables": [
                {
                    "key": "requirements",
                    "id": "aaaaaaaa-0000-0000-0000-000000000001",
                    "name": "Requirements",
                    "description": None,
                    "status": "AWAITING_APPROVAL",
                    "activities": [
                        {
                            "key": "elicit",
                            "id": "bbbbbbbb-0000-0000-0000-000000000001",
                            "name": "Elicit needs",
                            "description": "",
                            "status": "COMPLETED",
                            "output": "## Needs\nThings.",
                            "depends_on": [],
                            "required_capabilities": [
                                {
                                    "name": "Business Analysis",
                                    "description": "",
                                    "minimum_level": 2,
                                    "mandatory": True,
                                }
                            ],
                        }
                    ],
                    "versions": [
                        {
                            "version": 1,
                            "content": "# Requirements\n\n## Needs\nThings.",
                            "filename": "requirements-v1.md",
                            "created_by": "Claude",
                            "created_at": "2026-01-01T00:00:00+00:00",
                            "review_summary": None,
                        }
                    ],
                }
            ],
        },
        "execution_plan": {
            "activity_order": ["elicit"],
            "deliverable_order": ["requirements"],
            "allocations": [
                {
                    "activity_key": "elicit",
                    "resource": {
                        "type": "AIResource",
                        "name": "Claude",
                        "provider": "Anthropic",
                        "model": "claude-opus-4",
                        "capabilities": [
                            {
                                "name": "Business Analysis",
                                "description": "",
                                "level": 4,
                            }
                        ],
                    },
                }
            ],
        },
        "execution_result": {
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:01:00+00:00",
            "status": "AWAITING_APPROVAL",
            "messages": ["Activity 'elicit' completed by 'Claude'."],
            "activities_executed": 1,
            "deliverables_produced": ["requirements-v1.md"],
        },
    }


def v3_payload() -> dict:
    """Version 3: methodologies exist, but gates lived in the registry."""
    payload = upgrade(v1_payload(), 3)
    payload["execution_plan"]["methodology"] = "business-analysis"
    payload["analysis"]["deliverables"][0]["stage"] = "discovery"

    return payload


# ------------------------------------------------------------- each hop


def test_v1_gives_the_mission_an_identity():
    upgraded = upgrade(v1_payload(), 2)

    mission = upgraded["mission"]

    assert mission["id"]
    assert mission["status"] == "LAUNCHED"
    assert mission["priority"] == "MEDIUM"
    assert mission["project_id"] == PROJECT_ID


def test_v1_constraints_gain_a_type_rather_than_being_dropped():
    upgraded = upgrade(v1_payload(), 2)

    constraint = upgraded["mission"]["constraints"][0]

    assert constraint["description"] == "Must ship in Q3"
    assert constraint["type"] == "OTHER"


def test_v2_marks_pre_methodology_work_as_having_no_stage():
    upgraded = upgrade(v1_payload(), 3)

    deliverable = upgraded["analysis"]["deliverables"][0]

    assert deliverable["stage"] is None
    assert deliverable["sections"] == []
    assert deliverable["activities"][0]["technique"] is None


def test_v3_moves_the_work_onto_the_plan():
    upgraded = upgrade(v3_payload(), 4)

    assert "deliverables" not in upgraded["analysis"]
    assert [d["key"] for d in upgraded["execution_plan"]["deliverables"]] == [
        "requirements"
    ]
    assert upgraded["execution_plan"]["methodology_key"] == "business-analysis"


def test_v3_does_not_invent_the_gates_it_cannot_recover(caplog):
    """
    Reconstructing gates from today's registry would hold an engagement to
    rules it was never planned under. Absent and reported beats invented.
    """
    with caplog.at_level("WARNING"):
        upgraded = upgrade(v3_payload(), 4)

    assert upgraded["execution_plan"]["stages"] == []
    assert "without stage gates" in caplog.text


# ---------------------------------------------------------- whole chain


def test_a_version_1_engagement_loads_today():
    project = ProjectSerializer().from_dict(v1_payload())

    assert project.mission.title == "Reduce onboarding time"
    assert project.mission.constraints[0].description == "Must ship in Q3"
    assert [d.key for d in project.deliverables] == ["requirements"]

    activity = project.execution_plan.activity_by_key("elicit")

    assert activity.is_completed
    assert activity.output == "## Needs\nThings."
    assert project.execution_plan.get_resource(activity).name == "Claude"


def test_the_deliverable_and_its_version_survive_the_whole_chain():
    project = ProjectSerializer().from_dict(v1_payload())

    version = project.deliverable("requirements").latest_version()

    assert version.version == 1
    assert version.filename == "requirements-v1.md"
    assert "Things." in version.content


def test_an_upgraded_engagement_can_be_saved_and_reloaded(tmp_path):
    repository = ProjectRepository(tmp_path / "state")
    path = (tmp_path / "state")
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{PROJECT_ID}.json").write_text(
        json.dumps(v1_payload()), encoding="utf-8"
    )

    from uuid import UUID

    project = repository.load(UUID(PROJECT_ID))
    repository.save(project)

    saved = json.loads((path / f"{PROJECT_ID}.json").read_text(encoding="utf-8"))

    assert saved["schema_version"] == SCHEMA_VERSION
    assert repository.load(UUID(PROJECT_ID)).mission.title == (
        "Reduce onboarding time"
    )


# --------------------------------------------------------------- refusal


def test_a_file_from_the_future_is_refused():
    payload = {"schema_version": SCHEMA_VERSION + 1, "id": PROJECT_ID}

    with pytest.raises(SchemaError, match="newer than this build"):
        upgrade(payload, SCHEMA_VERSION)


def test_a_file_with_no_version_is_refused():
    with pytest.raises(SchemaError, match="no usable schema version"):
        upgrade({"id": PROJECT_ID}, SCHEMA_VERSION)


def test_every_version_has_a_migration_to_the_next():
    """A schema bump without a migration should fail here, not in the field."""
    from infrastructure.persistence.migrations import _MIGRATIONS

    missing = [
        version
        for version in range(1, SCHEMA_VERSION)
        if version not in _MIGRATIONS
    ]

    assert not missing, (
        f"No migration defined from schema version(s) {missing}. "
        f"Every bump needs one."
    )
