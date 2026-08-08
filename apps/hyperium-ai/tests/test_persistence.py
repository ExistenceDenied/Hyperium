"""
Persistence coverage.

The approval gate is only real if the process can exit while a human decides.
These tests save an engagement, throw the objects away, reload from disk and
carry on.
"""

import pytest

from application.project.project_builder import ProjectBuilder
from core.execution.deliverable_status import DeliverableStatus
from core.execution.execution_result import ExecutionStatus
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.project_repository import ProjectRepository
from infrastructure.persistence.project_serializer import ProjectSerializer
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


def start(tmp_path):
    repository = ProjectRepository(tmp_path / "state")
    llm = ScriptedLLM()
    store = InMemoryArtifactStore()

    project = ProjectBuilder.build(
        llm, store, repository=repository, methodologies=FakeMethodologies()
    ).start(
        build_mission(),
        resources=[build_consultant()],
    )

    return project, repository, llm, store


def test_starting_an_engagement_writes_it_to_disk(tmp_path):
    project, repository, _, _ = start(tmp_path)

    assert repository.exists(project.id)
    assert repository.list_ids() == [project.id]


def test_round_trip_preserves_the_whole_engagement(tmp_path):
    project, repository, _, _ = start(tmp_path)

    restored = repository.load(project.id)

    assert restored.id == project.id
    assert restored.mission.title == project.mission.title
    assert restored.mission.objective.description == (
        project.mission.objective.description
    )
    assert [d.key for d in restored.deliverables] == [
        d.key for d in project.deliverables
    ]
    assert [a.key for a in restored.execution_plan.activities] == [
        a.key for a in project.execution_plan.activities
    ]
    assert restored.execution_result.status is ExecutionStatus.AWAITING_APPROVAL


def test_round_trip_preserves_activity_progress(tmp_path):
    project, repository, _, _ = start(tmp_path)

    restored = repository.load(project.id)

    elicit = restored.execution_plan.activity_by_key("elicit")
    downstream = restored.execution_plan.activity_by_key("design-curriculum")

    assert elicit.is_completed
    assert elicit.output
    assert not downstream.is_completed
    assert downstream.depends_on == {"elicit"}


def test_round_trip_preserves_deliverable_versions_and_status(tmp_path):
    project, repository, _, _ = start(tmp_path)

    restored = repository.load(project.id)
    requirements = restored.deliverable("requirements")

    assert requirements.status is DeliverableStatus.AWAITING_APPROVAL
    assert requirements.latest_version().filename == "requirements-v1.md"
    assert (
        requirements.latest_version().content
        == project.deliverable("requirements").latest_version().content
    )


def test_round_trip_preserves_resource_allocations(tmp_path):
    project, repository, _, _ = start(tmp_path)

    restored = repository.load(project.id)
    activity = restored.execution_plan.activity_by_key("elicit")

    resource = restored.execution_plan.get_resource(activity)

    assert resource is not None
    assert resource.name == "Claude"
    assert resource.capabilities


def test_an_engagement_resumes_in_a_fresh_process(tmp_path):
    """
    The important one: nothing from the first run stays in memory.
    """
    project, repository, _, _ = start(tmp_path)
    project_id = project.id

    del project

    reloaded = repository.load(project_id)
    reloaded.approve("requirements", summary="Approved after review.")
    repository.save(reloaded)

    del reloaded

    resumed = repository.load(project_id)
    service = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=repository,
        methodologies=FakeMethodologies(),
    )

    finished = service.resume(resumed)

    assert finished.deliverable("requirements").is_approved
    assert finished.deliverable("curriculum").latest_version() is not None
    assert finished.execution_result.activities_executed == 1


def test_loading_an_unknown_engagement_fails_clearly(tmp_path):
    repository = ProjectRepository(tmp_path / "state")

    with pytest.raises(FileNotFoundError, match="No saved engagement"):
        repository.load(build_consultant_id())


def build_consultant_id():
    from uuid import uuid4

    return uuid4()


def test_rejects_an_unsupported_schema_version():
    with pytest.raises(ValueError, match="schema version"):
        ProjectSerializer().from_dict({"schema_version": 99})


def test_the_plan_and_its_gates_survive_a_round_trip(tmp_path):
    """
    Without this the gates vanish on reload and a resumed engagement would
    happily run work its quality gate should have blocked.
    """
    repository = ProjectRepository(tmp_path / "state")

    project = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=repository,
        methodologies=FakeMethodologies(),
    ).start(build_mission(), resources=[build_consultant()])

    restored = repository.load(project.id)

    assert restored.execution_plan.methodology_key == "test-two-stage"
    assert [s.key for s in restored.execution_plan.stages] == [
        "discovery",
        "design",
    ]
    assert restored.deliverable("requirements").stage == "discovery"
    assert restored.deliverable("requirements").sections == (
        "Learning needs",
        "Constraints",
    )
    assert not restored.execution_plan.gate_result("discovery").passed


def test_gates_survive_the_methodology_being_deleted(tmp_path):
    """
    Regression: gates used to be resolved from the registry at read time, so
    renaming or removing a methodology silently opened every gate on every
    engagement already in flight. The plan now owns the gates it was planned
    with, and governance cannot be edited out from under a running engagement.
    """
    repository = ProjectRepository(tmp_path / "state")

    project = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=repository,
        methodologies=FakeMethodologies(),
    ).start(build_mission(), resources=[build_consultant()])

    # The methodology is gone entirely; the repository never consults one.
    restored = ProjectRepository(tmp_path / "state").load(project.id)

    gate = restored.execution_plan.gate_result("discovery")

    assert not gate.passed
    assert "has not been approved" in gate.failures[0]
    assert len(restored.execution_plan.activities) == 2


def test_a_plan_referencing_missing_work_fails_loudly(tmp_path):
    """Silently dropping work would leave a smaller engagement than was saved."""
    import json

    repository = ProjectRepository(tmp_path / "state")

    project = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=repository,
        methodologies=FakeMethodologies(),
    ).start(build_mission(), resources=[build_consultant()])

    path = (tmp_path / "state") / f"{project.id}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["execution_plan"]["activity_order"].append("ghost-activity")
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="ghost-activity"):
        repository.load(project.id)
