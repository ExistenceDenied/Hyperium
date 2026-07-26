from __future__ import annotations

from pathlib import Path
from uuid import UUID

from core.agents.agent_result import AgentResult
from core.agents.task_record import TaskRecord

# The tools that produce a file, each keyed under a "path" argument. Used to
# work out where a task's deliverable ended up, so a person can open it.
_FILE_TOOLS = {
    "write_file",
    "write_excel",
    "update_excel_cell",
    "write_word",
    "write_powerpoint",
}


def deliverables_from(steps, root=None) -> list[str]:
    """Absolute paths of the files a run produced, in order, de-duplicated."""
    base = Path(root) if root else Path(".")
    paths: list[str] = []

    for step in steps or []:
        if step.tool not in _FILE_TOOLS:
            continue
        if step.result.startswith(("Error", "Denied")):
            continue  # nothing was written

        raw = str(step.arguments.get("path", "")).strip()
        if not raw:
            continue

        absolute = str((base / raw).resolve())
        if absolute not in paths:
            paths.append(absolute)

    return paths


class TaskService:
    """
    Records direct-task runs and reads them back.

    The repository is duck-typed, exactly as the backlog service takes its own:
    the application layer never imports infrastructure. Whatever is passed need
    only offer save / get / list over TaskRecord.
    """

    def __init__(self, repository) -> None:
        self._repository = repository

    def record(
        self,
        prompt: str,
        result: AgentResult,
        model: str | None = None,
        root=None,
        priority: str = "medium",
    ) -> TaskRecord:
        from datetime import datetime, timezone

        record = TaskRecord(
            prompt=prompt,
            model=model,
            result=result,
            artifacts=deliverables_from(result.steps, root),
            priority=priority,
            completed_at=datetime.now(timezone.utc),
        )
        self._repository.save(record)

        return record

    def get(self, task_id: UUID) -> TaskRecord:
        return self._repository.get(task_id)

    def list(self) -> list[TaskRecord]:
        return self._repository.list()
