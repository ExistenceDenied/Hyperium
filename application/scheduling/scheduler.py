from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class Scheduler:
    """
    Runs due schedules on a clock by putting their tasks on the queue.

    It never runs a task itself — it enqueues, and the worker launches. That
    keeps one path to execution (the queue) and one place that respects capacity
    and approval. `tick` is pure enough to test; `start` just calls it on a loop.
    """

    def __init__(self, store, enqueue: Callable[..., object]) -> None:
        self._store = store
        self._enqueue = enqueue

    def tick(self, now: datetime | None = None) -> int:
        now = now or datetime.now(timezone.utc)
        fired = 0
        for schedule in self._store.list():
            if not schedule.is_due(now):
                continue
            self._enqueue(
                schedule.prompt,
                priority=schedule.priority,
                technique=schedule.technique,
                methodology=schedule.methodology,
            )
            self._store.mark_run(schedule.id, now)
            fired += 1
        return fired

    def start(self, interval: float = 60.0) -> None:
        def loop() -> None:
            while True:
                try:
                    self.tick()
                except Exception:  # never let the clock die on one bad tick
                    logger.exception("scheduler tick failed")
                time.sleep(interval)

        threading.Thread(target=loop, daemon=True).start()
