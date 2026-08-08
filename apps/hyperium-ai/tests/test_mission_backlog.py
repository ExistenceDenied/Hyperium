"""
Mission backlog: CRUD, lifecycle and launch.

The design point being pinned here is that a mission may be captured
incomplete and refined over time — validation is enforced at launch, not at
save — and that a launched mission is frozen so the backlog cannot drift away
from the engagement that was actually run.
"""

from datetime import datetime, timezone

import pytest

from application.missions.mission_backlog_service import MissionBacklogService
from application.project.project_builder import ProjectBuilder
from core.missions.mission import MissionStateError
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.mission_repository import (
    MissionNotFoundError,
    MissionRepository,
)
from tests.fixtures import FakeMethodologies, ScriptedLLM, build_consultant


def build_backlog(tmp_path, with_execution=True):
    repository = MissionRepository(tmp_path / "missions")

    project_service = None

    if with_execution:
        project_service = ProjectBuilder.build(
            ScriptedLLM(),
            InMemoryArtifactStore(),
            methodologies=FakeMethodologies(),
        )

    return MissionBacklogService(repository, project_service), repository


def add(backlog, title="Onboarding Redesign", criteria=("Time halved.",), **kw):
    return backlog.create(
        title=title,
        objective="Cut time-to-first-value in half.",
        criteria=list(criteria),
        **kw,
    )


# ------------------------------------------------------------------ create


def test_a_mission_is_added_as_a_draft(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)

    assert mission.status is MissionStatus.DRAFT
    assert mission.priority is MissionPriority.MEDIUM
    assert mission.id is not None


def test_an_incomplete_mission_can_be_captured(tmp_path):
    """A backlog that rejects half-formed ideas is not a backlog."""
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog, criteria=[])

    assert mission.success_criteria == []
    assert not mission.is_complete
    assert mission.status is MissionStatus.DRAFT


def test_creating_rejects_an_empty_title_or_objective(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    with pytest.raises(ValueError, match="title is required"):
        backlog.create(title="   ", objective="Something.")

    with pytest.raises(ValueError, match="objective is required"):
        backlog.create(title="Something", objective="  ")


def test_constraints_and_stakeholders_are_recorded(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = backlog.create(
        title="Onboarding",
        objective="Cut time in half.",
        constraints=["TIME: Must ship in Q3"],
        stakeholders=["Priya: Head of CS"],
    )

    assert mission.constraints[0].description == "Must ship in Q3"
    assert mission.constraints[0].type.name == "TIME"
    assert mission.stakeholders[0].name == "Priya"


def test_an_unrecognised_category_is_kept_rather_than_rejected(tmp_path):
    """
    "COST: under budget" is an ordinary thing to write. Rejecting a whole
    mission because the category is not in the enum is hostile; categories
    sort constraints, they do not gatekeep them.
    """
    backlog, _ = build_backlog(tmp_path)

    mission = backlog.create(
        title="X",
        objective="Y",
        constraints=["COST: under budget", "Must be sunny"],
    )

    assert [c.description for c in mission.constraints] == [
        "COST: under budget",
        "Must be sunny",
    ]
    assert {c.type.name for c in mission.constraints} == {"OTHER"}


def test_a_known_category_is_still_recognised(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = backlog.create(
        title="X",
        objective="Y",
        constraints=["legal: GDPR applies"],
    )

    assert mission.constraints[0].type.name == "LEGAL"
    assert mission.constraints[0].description == "GDPR applies"


def test_a_stakeholder_still_needs_a_role(tmp_path):
    """Both halves carry meaning and neither can be inferred."""
    backlog, _ = build_backlog(tmp_path)

    with pytest.raises(ValueError, match="Name: role"):
        backlog.create(title="X", objective="Y", stakeholders=["just a name"])


# -------------------------------------------------------------------- read


def test_a_mission_survives_a_round_trip(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    created = backlog.create(
        title="Onboarding",
        objective="Cut time in half.",
        priority=MissionPriority.HIGH,
        criteria=["Time halved."],
        constraints=["TIME: Q3"],
        stakeholders=["Priya: Head of CS"],
    )

    loaded = backlog.get(created.id)

    assert loaded.id == created.id
    assert loaded.title == created.title
    assert loaded.priority is MissionPriority.HIGH
    assert loaded.objective.description == created.objective.description
    assert [c.description for c in loaded.success_criteria] == ["Time halved."]
    assert loaded.constraints[0].type.name == "TIME"
    assert loaded.stakeholders[0].role == "Head of CS"


def test_the_backlog_is_ordered_by_priority(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    add(backlog, title="Low", priority=MissionPriority.LOW)
    add(backlog, title="Critical", priority=MissionPriority.CRITICAL)
    add(backlog, title="Medium", priority=MissionPriority.MEDIUM)
    add(backlog, title="High", priority=MissionPriority.HIGH)

    titles = [item.title for item in backlog.list()]

    assert titles == ["Critical", "High", "Medium", "Low"]


def test_missions_of_equal_priority_are_ordered_oldest_first(tmp_path):
    backlog, repository = build_backlog(tmp_path)

    newer = add(backlog, title="Newer")
    older = add(backlog, title="Older")

    # Set the timestamps explicitly: missions created in the same clock tick
    # would otherwise tie, and the test would be asserting luck.
    newer.created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
    older.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    repository.save(newer)
    repository.save(older)

    assert [item.title for item in backlog.list()] == ["Older", "Newer"]


def test_backlog_order_is_stable_across_reads(tmp_path):
    """Regression: ties used to fall back to random UUID filename order."""
    backlog, _ = build_backlog(tmp_path)

    for index in range(6):
        add(backlog, title=f"Mission {index}")

    assert [m.id for m in backlog.list()] == [m.id for m in backlog.list()]


def test_listing_can_filter_by_status(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    keep = add(backlog, title="Keep")
    add(backlog, title="Shelve")

    backlog.mark_ready(keep.id)

    ready = backlog.list(status=MissionStatus.READY)

    assert [item.title for item in ready] == ["Keep"]


def test_archived_missions_are_hidden_unless_asked_for(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    shelved = add(backlog, title="Shelve")
    backlog.archive(shelved.id)

    assert [m.title for m in backlog.list()] == []
    assert [m.title for m in backlog.list(include_archived=True)] == ["Shelve"]


def test_reading_an_unknown_mission_fails_clearly(tmp_path):
    backlog, _ = build_backlog(tmp_path)
    from uuid import uuid4

    with pytest.raises(MissionNotFoundError, match="No mission"):
        backlog.get(uuid4())


# ------------------------------------------------------------------ update


def test_a_mission_can_be_refined(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog, criteria=[])

    updated = backlog.update(
        mission.id,
        title="Onboarding Redesign v2",
        objective="Cut time-to-first-value by 60%.",
        priority=MissionPriority.CRITICAL,
        add_criteria=["Time cut by 60%."],
    )

    assert updated.title == "Onboarding Redesign v2"
    assert updated.priority is MissionPriority.CRITICAL
    assert updated.is_complete
    assert backlog.get(mission.id).title == "Onboarding Redesign v2"


def test_criteria_can_be_replaced(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog, criteria=["Old one."])

    updated = backlog.update(
        mission.id,
        clear_criteria=True,
        add_criteria=["New one."],
    )

    assert [c.description for c in updated.success_criteria] == ["New one."]


def test_updating_rejects_blanking_a_required_field(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)

    with pytest.raises(ValueError, match="title cannot be empty"):
        backlog.update(mission.id, title="  ")


def test_marking_ready_requires_a_complete_mission(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog, criteria=[])

    with pytest.raises(Exception, match="success criterion"):
        backlog.mark_ready(mission.id)


def test_an_archived_mission_can_be_restored(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.archive(mission.id)

    assert backlog.restore(mission.id).status is MissionStatus.DRAFT


# ------------------------------------------------------------------ delete


def test_a_mission_can_be_deleted(tmp_path):
    backlog, repository = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.delete(mission.id)

    assert not repository.exists(mission.id)
    assert backlog.list() == []


def test_deleting_a_launched_mission_is_refused_by_default(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.launch(mission.id, resources=[build_consultant()])

    with pytest.raises(MissionStateError, match="orphans that engagement"):
        backlog.delete(mission.id)


def test_deleting_a_launched_mission_is_possible_with_force(tmp_path):
    backlog, repository = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.launch(mission.id, resources=[build_consultant()])
    backlog.delete(mission.id, force=True)

    assert not repository.exists(mission.id)


# ------------------------------------------------------------------ launch


def test_launching_runs_the_engagement_and_links_it_back(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    project = backlog.launch(mission.id, resources=[build_consultant()])

    stored = backlog.get(mission.id)

    assert stored.status is MissionStatus.LAUNCHED
    assert stored.project_id == project.id
    assert project.deliverable("requirements").latest_version() is not None


def test_launching_an_incomplete_mission_is_refused(tmp_path):
    """Validation is deferred to launch — this is where it bites."""
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog, criteria=[])

    with pytest.raises(Exception, match="success criterion"):
        backlog.launch(mission.id, resources=[build_consultant()])

    assert backlog.get(mission.id).status is MissionStatus.DRAFT


def test_a_mission_cannot_be_launched_twice(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.launch(mission.id, resources=[build_consultant()])

    with pytest.raises(MissionStateError, match="already launched"):
        backlog.launch(mission.id, resources=[build_consultant()])


def test_an_archived_mission_cannot_be_launched(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.archive(mission.id)

    with pytest.raises(MissionStateError, match="archived"):
        backlog.launch(mission.id, resources=[build_consultant()])


def test_a_launched_mission_is_frozen(tmp_path):
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.launch(mission.id, resources=[build_consultant()])

    with pytest.raises(MissionStateError, match="cannot be edited"):
        backlog.update(mission.id, title="Changed my mind")


def test_priority_can_still_be_changed_after_launch(tmp_path):
    """Reprioritising does not desynchronise the engagement snapshot."""
    backlog, _ = build_backlog(tmp_path)

    mission = add(backlog)
    backlog.launch(mission.id, resources=[build_consultant()])

    updated = backlog.update(mission.id, priority=MissionPriority.LOW)

    assert updated.priority is MissionPriority.LOW


def test_a_backlog_without_execution_cannot_launch(tmp_path):
    backlog, _ = build_backlog(tmp_path, with_execution=False)

    mission = add(backlog)

    with pytest.raises(RuntimeError, match="cannot launch"):
        backlog.launch(mission.id, resources=[build_consultant()])
