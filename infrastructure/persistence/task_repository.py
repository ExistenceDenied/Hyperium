from __future__ import annotations

import json
import threading
from pathlib import Path
from uuid import UUID

from core.agents.task_record import TaskRecord
from infrastructure.json_store import write_json_atomic
from infrastructure.persistence.task_serializer import (
    SCHEMA_VERSION,
    TaskSerializer,
)


class TaskNotFoundError(KeyError):
    """Raised when a task id has no saved record."""


class TaskRepository:
    """
    The direct-task log, stored as one JSON file per run.

    Mirrors the mission repository: schema-versioned payloads, one file per id,
    listings returned newest-first so the most recent work is what a caller
    sees without having to sort.
    """

    def __init__(self, root: Path, serializer: TaskSerializer | None = None) -> None:
        self._root = Path(root)
        self._serializer = serializer or TaskSerializer()
        # The same record is written from a task's execution thread and from web
        # requests (adding a note); serialize the writes and make each atomic.
        self._lock = threading.Lock()

    def save(self, record: TaskRecord) -> Path:
        path = self._path(record.id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            **self._serializer.to_dict(record),
        }
        with self._lock:
            write_json_atomic(path, payload)
        return path

    def get(self, task_id: UUID) -> TaskRecord:
        path = self._path(task_id)

        if not path.exists():
            raise TaskNotFoundError(f"No task '{task_id}' has been saved.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        version = payload.get("schema_version")

        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported task schema version {version!r}; "
                f"expected {SCHEMA_VERSION}."
            )

        return self._serializer.from_dict(payload)

    def list(self) -> list[TaskRecord]:
        records = [self.get(item) for item in self._ids()]

        # Newest first, with the id breaking ties so two runs in the same clock
        # tick still order deterministically rather than by filesystem chance.
        return sorted(
            records,
            key=lambda record: (record.created_at, str(record.id)),
            reverse=True,
        )

    def _ids(self) -> list[UUID]:
        if not self._root.exists():
            return []

        ids = []

        for path in sorted(self._root.glob("*.json")):
            try:
                ids.append(UUID(path.stem))
            except ValueError:
                continue

        return ids

    def _path(self, task_id: UUID) -> Path:
        return self._root / f"{task_id}.json"
