from __future__ import annotations

from uuid import UUID

from core.agents.agent_result import AgentResult
from core.agents.task_record import TaskRecord


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
    ) -> TaskRecord:
        record = TaskRecord(prompt=prompt, model=model, result=result)
        self._repository.save(record)

        return record

    def get(self, task_id: UUID) -> TaskRecord:
        return self._repository.get(task_id)

    def list(self) -> list[TaskRecord]:
        return self._repository.list()
