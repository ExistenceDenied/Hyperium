from __future__ import annotations

import json
import logging
import re

from core.interfaces.llm_provider import LLMProvider

logger = logging.getLogger(__name__)

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON = re.compile(r"\{.*\}", re.DOTALL)

_CRITIC = """\
You are a demanding reviewer assessing a business deliverable before it reaches \
a client. Judge whether it is genuinely client-ready: specific and substantive, \
well-structured, complete, and free of placeholders, filler or vague \
generalities. If it is already strong, say so honestly — do not invent faults. \
Otherwise give concrete, actionable improvements: what to add, sharpen, \
restructure or cut. Direct the improvements; do not rewrite it yourself."""


class QualityCritic:
    """
    Judges a produced deliverable and says how to make it better.

    This is what lets a task improve its own work: it reads the actual content of
    what was produced and returns concrete feedback, or nothing when the work is
    already good. A refining runner feeds that feedback back to the agent for
    another pass, so quality rises with the time spent rather than stopping at
    the first draft.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def critique(self, task: str, content: str) -> str:
        """Feedback to improve the deliverable, or '' when it is good enough."""
        if not content.strip():
            return ""
        try:
            response = self._llm.generate(self._prompt(task, content))
        except Exception:
            logger.warning("Quality critic call failed.")
            return ""
        return self._parse(response)

    def _prompt(self, task: str, content: str) -> str:
        return "\n".join(
            [
                _CRITIC,
                "",
                "# The task",
                task,
                "",
                "# The deliverable produced",
                content[:6000],
                "",
                "Respond with a single JSON object and nothing else:",
                '{"good_enough": true/false, "feedback": "specific improvements, '
                'or empty if good enough"}',
            ]
        )

    def _parse(self, response: str) -> str:
        text = _THINK.sub("", response or "").strip()
        match = _JSON.search(text)
        if match is None:
            return ""
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return ""
        if data.get("good_enough") is True:
            return ""
        return str(data.get("feedback", "")).strip()
