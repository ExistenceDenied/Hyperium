from __future__ import annotations

import dataclasses

import pytest

from core.agents.agent_result import AgentResult, AgentStep, StopReason
from core.agents.task_record import TaskRecord
from infrastructure.persistence.task_repository import (
    TaskNotFoundError,
    TaskRepository,
)
from infrastructure.persistence.task_serializer import TaskSerializer


def sample_record() -> TaskRecord:
    result = AgentResult(
        output="Done.",
        steps=[
            AgentStep(tool="read_file", arguments={"path": "a.txt"}, result="hi")
        ],
        stop_reason=StopReason.COMPLETED,
    )

    return TaskRecord(prompt="summarize a.txt", model="qwen3:latest", result=result)


# ---------------------------------------------------------- field coverage


def test_task_record_fields_are_persisted():
    payload = TaskSerializer().to_dict(sample_record())

    declared = {field.name for field in dataclasses.fields(TaskRecord)}
    missing = declared - set(payload)

    assert not missing, (
        f"TaskRecord fields are not persisted: {sorted(missing)}. "
        "Add them to TaskSerializer and bump SCHEMA_VERSION."
    )


def test_agent_result_and_step_fields_are_persisted():
    payload = TaskSerializer().to_dict(sample_record())
    result_node = payload["result"]

    result_missing = {
        field.name for field in dataclasses.fields(AgentResult)
    } - set(result_node)
    step_missing = {
        field.name for field in dataclasses.fields(AgentStep)
    } - set(result_node["steps"][0])

    assert not result_missing, sorted(result_missing)
    assert not step_missing, sorted(step_missing)


# --------------------------------------------------------- value round-trip


def test_a_record_survives_a_round_trip():
    serializer = TaskSerializer()
    original = sample_record()

    restored = serializer.from_dict(serializer.to_dict(original))

    assert restored.id == original.id
    assert restored.prompt == original.prompt
    assert restored.model == original.model
    assert restored.created_at == original.created_at
    assert restored.result.output == "Done."
    assert restored.result.stop_reason is StopReason.COMPLETED
    assert restored.result.steps[0].tool == "read_file"
    assert restored.result.steps[0].arguments == {"path": "a.txt"}


# ------------------------------------------------------------- repository


def test_repository_saves_and_reads_back(tmp_path):
    repo = TaskRepository(tmp_path)
    record = sample_record()

    repo.save(record)

    assert repo.get(record.id).prompt == "summarize a.txt"


def test_missing_task_raises(tmp_path):
    repo = TaskRepository(tmp_path)

    with pytest.raises(TaskNotFoundError):
        repo.get(sample_record().id)


def test_listing_is_newest_first(tmp_path):
    from datetime import datetime, timezone

    repo = TaskRepository(tmp_path)
    older = TaskRecord(
        prompt="older",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        result=AgentResult(output="a"),
    )
    newer = TaskRecord(
        prompt="newer",
        created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        result=AgentResult(output="b"),
    )
    repo.save(older)
    repo.save(newer)

    listed = repo.list()

    assert [record.prompt for record in listed] == ["newer", "older"]


def test_status_reflects_the_outcome():
    completed = sample_record()
    assert completed.status == "completed"
    assert completed.acted is True

    empty = TaskRecord(prompt="x")
    assert empty.status == "pending"
    assert empty.acted is False
