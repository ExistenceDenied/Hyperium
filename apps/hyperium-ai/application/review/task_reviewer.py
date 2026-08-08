from __future__ import annotations

import logging

from core.interfaces.llm_provider import LLMProvider
from core.llm_parsing import extract_json_object

logger = logging.getLogger(__name__)


class TaskReviewer:
    """
    Reviews a finished task and proposes concrete follow-up tasks.

    This is what lets the system improve its own work: given what was asked and
    what came back, it returns a short list of self-contained instructions that
    would improve or extend the result, which are then queued for the worker to
    run. If the work is already good, it returns nothing.
    """

    def __init__(self, llm: LLMProvider, limit: int = 3) -> None:
        self._llm = llm
        self._limit = limit

    def review(self, prompt: str, output: str) -> list[str]:
        try:
            response = self._llm.generate(self._prompt(prompt, output))
        except Exception:
            logger.warning("Task reviewer call failed.")
            return []

        return self._parse(response)

    def _prompt(self, prompt: str, output: str) -> str:
        return "\n".join(
            [
                "You are a demanding reviewer. A task was completed. Propose up "
                f"to {self._limit} specific, actionable follow-up tasks that "
                "would meaningfully improve or extend the result. Each must be a "
                "self-contained instruction an agent could carry out on its own. "
                "If the work is already excellent and nothing worthwhile remains, "
                "return an empty list — do not invent busywork.",
                "",
                "# The task",
                prompt,
                "",
                "# The result",
                output[:4000],
                "",
                "Respond with a single JSON object and nothing else:",
                '{"tasks": ["first follow-up task", "second follow-up task"]}',
            ]
        )

    def _parse(self, response: str) -> list[str]:
        payload = extract_json_object(response)
        if payload is None:
            return []

        tasks = payload.get("tasks", [])
        if not isinstance(tasks, list):
            return []

        return [str(task).strip() for task in tasks if str(task).strip()][: self._limit]
