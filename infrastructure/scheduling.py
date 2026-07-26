from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from core.scheduling.schedule import Schedule


class ScheduleStore:
    """
    The recurring tasks the system runs on a clock, held in one JSON file.

    A schedule is a standing instruction ("every day, summarise yesterday's
    invoices"); the scheduler consults this store, and when one is due it puts a
    task on the queue for the worker to run.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def list(self) -> list[Schedule]:
        return [self._from_dict(item) for item in self._read()]

    def get(self, schedule_id: UUID) -> Schedule | None:
        for schedule in self.list():
            if schedule.id == schedule_id:
                return schedule
        return None

    def add(
        self,
        prompt: str,
        every_hours: int = 24,
        priority: str = "medium",
        technique: str = "",
        methodology: str = "",
    ) -> Schedule:
        schedule = Schedule(
            prompt=prompt.strip(),
            every_hours=int(every_hours),
            priority=priority,
            technique=technique,
            methodology=methodology,
        )
        data = self._read()
        data.append(self._to_dict(schedule))
        self._write(data)
        return schedule

    def set_enabled(self, schedule_id: UUID, enabled: bool) -> None:
        data = self._read()
        for item in data:
            if item["id"] == str(schedule_id):
                item["enabled"] = bool(enabled)
        self._write(data)

    def mark_run(self, schedule_id: UUID, at: datetime) -> None:
        data = self._read()
        for item in data:
            if item["id"] == str(schedule_id):
                item["last_run"] = at.isoformat()
        self._write(data)

    def delete(self, schedule_id: UUID) -> None:
        self._write(
            [item for item in self._read() if item["id"] != str(schedule_id)]
        )

    # --------------------------------------------------------- internals

    def _read(self) -> list[dict]:
        if not self._path.is_file():
            return []
        return json.loads(self._path.read_text(encoding="utf-8")).get("schedules", [])

    def _write(self, schedules: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"schedules": schedules}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _to_dict(self, schedule: Schedule) -> dict:
        return {
            "id": str(schedule.id),
            "prompt": schedule.prompt,
            "every_hours": schedule.every_hours,
            "priority": schedule.priority,
            "technique": schedule.technique,
            "methodology": schedule.methodology,
            "enabled": schedule.enabled,
            "last_run": schedule.last_run.isoformat() if schedule.last_run else None,
            "created_at": schedule.created_at.isoformat(),
        }

    def _from_dict(self, data: dict) -> Schedule:
        last_run = data.get("last_run")
        return Schedule(
            prompt=data["prompt"],
            id=UUID(data["id"]),
            every_hours=int(data.get("every_hours", 24)),
            priority=data.get("priority", "medium"),
            technique=data.get("technique", ""),
            methodology=data.get("methodology", ""),
            enabled=data.get("enabled", True),
            last_run=datetime.fromisoformat(last_run) if last_run else None,
            created_at=datetime.fromisoformat(data["created_at"]),
        )
