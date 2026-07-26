from __future__ import annotations

from datetime import datetime, timedelta, timezone

from application.scheduling.scheduler import Scheduler
from core.scheduling.schedule import Schedule
from infrastructure.scheduling import ScheduleStore


def _at(hours: int = 0) -> datetime:
    return datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(hours=hours)


def test_a_new_schedule_is_due_immediately_then_waits(tmp_path):
    schedule = Schedule(prompt="do it", every_hours=24)

    assert schedule.is_due(_at(0)) is True  # never run

    schedule.last_run = _at(0)
    assert schedule.is_due(_at(1)) is False  # too soon
    assert schedule.is_due(_at(24)) is True  # a day later


def test_disabled_schedules_are_never_due():
    schedule = Schedule(prompt="do it", enabled=False)
    assert schedule.is_due(_at(100)) is False


def test_store_round_trips_a_schedule(tmp_path):
    store = ScheduleStore(tmp_path / "s.json")

    created = store.add("weekly report", every_hours=168, priority="high")
    store.mark_run(created.id, _at(5))

    reloaded = store.get(created.id)
    assert reloaded.prompt == "weekly report"
    assert reloaded.every_hours == 168
    assert reloaded.priority == "high"
    assert reloaded.cadence == "weekly"
    assert reloaded.last_run == _at(5)

    store.set_enabled(created.id, False)
    assert store.get(created.id).enabled is False

    store.delete(created.id)
    assert store.list() == []


def test_scheduler_enqueues_due_tasks_and_marks_them_run(tmp_path):
    store = ScheduleStore(tmp_path / "s.json")
    store.add("due now", every_hours=24, priority="high", technique="swot")

    calls = []

    def enqueue(prompt, **kwargs):
        calls.append((prompt, kwargs))

    scheduler = Scheduler(store, enqueue)

    fired = scheduler.tick(_at(0))

    assert fired == 1
    assert calls[0][0] == "due now"
    assert calls[0][1]["priority"] == "high"
    assert calls[0][1]["technique"] == "swot"

    # Marked run, so a second tick a minute later does nothing.
    assert scheduler.tick(_at(0) + timedelta(minutes=1)) == 0
    # ...but a day later it fires again.
    assert scheduler.tick(_at(24)) == 1
