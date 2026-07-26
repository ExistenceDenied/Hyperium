from __future__ import annotations

from datetime import datetime, timezone

from core.agents.agent_result import AgentResult
from core.agents.task_record import Note, TaskRecord
from infrastructure.persistence.task_repository import TaskRepository
from infrastructure.persistence.task_serializer import TaskSerializer


def test_priority_notes_and_duration_round_trip():
    serializer = TaskSerializer()
    record = TaskRecord(
        prompt="write a quote",
        priority="high",
        created_at=datetime(2026, 1, 1, 9, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 1, 1, 9, 1, tzinfo=timezone.utc),
        notes=[Note(text="looks good", at=datetime(2026, 1, 1, tzinfo=timezone.utc))],
        result=AgentResult(output="done"),
    )

    restored = serializer.from_dict(serializer.to_dict(record))

    assert restored.priority == "high"
    assert restored.duration_seconds == 60
    assert restored.notes[0].text == "looks good"


def test_notes_persist_across_saves(tmp_path):
    repo = TaskRepository(tmp_path)
    record = TaskRecord(prompt="x", priority="low")
    repo.save(record)

    reloaded = repo.get(record.id)
    reloaded.notes.append(Note(text="a comment"))
    repo.save(reloaded)

    final = repo.get(record.id)
    assert final.priority == "low"
    assert final.notes[0].text == "a comment"


def test_duration_is_none_until_finished():
    assert TaskRecord(prompt="x").duration_seconds is None
