from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from core.agents.agent_result import AgentResult, AgentStep, StopReason
from core.agents.task_record import TaskRecord

SCHEMA_VERSION = 1


class TaskSerializer:
    """
    Converts a TaskRecord to and from plain dictionaries.

    Hand-written like the mission and project serializers, and held to the same
    standard: a field added to TaskRecord, AgentResult or AgentStep fails the
    completeness test until it is mapped here.
    """

    def to_dict(self, record: TaskRecord) -> dict[str, Any]:
        return {
            "id": str(record.id),
            "prompt": record.prompt,
            "created_at": record.created_at.isoformat(),
            "model": record.model,
            "result": self._result_to_dict(record.result),
        }

    def from_dict(self, payload: dict[str, Any]) -> TaskRecord:
        return TaskRecord(
            prompt=payload["prompt"],
            id=UUID(payload["id"]),
            created_at=datetime.fromisoformat(payload["created_at"]),
            model=payload.get("model"),
            result=self._result_from_dict(payload.get("result")),
        )

    def _result_to_dict(self, result: AgentResult | None) -> dict[str, Any] | None:
        if result is None:
            return None

        return {
            "output": result.output,
            "stop_reason": result.stop_reason.value,
            "steps": [
                {
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "result": step.result,
                }
                for step in result.steps
            ],
        }

    def _result_from_dict(self, data: dict[str, Any] | None) -> AgentResult | None:
        if not data:
            return None

        return AgentResult(
            output=data["output"],
            steps=[
                AgentStep(
                    tool=step["tool"],
                    arguments=step["arguments"],
                    result=step["result"],
                )
                for step in data.get("steps", [])
            ],
            stop_reason=StopReason(data["stop_reason"]),
        )
