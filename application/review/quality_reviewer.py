from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from core.execution.deliverable import Deliverable
from core.interfaces.llm_provider import LLMProvider
from core.missions.mission import Mission

logger = logging.getLogger(__name__)

_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


@dataclass(frozen=True)
class ReviewVerdict:
    """One reviewer's decision on a deliverable."""

    approved: bool
    feedback: str


class QualityReviewer:
    """
    An AI reviewer that judges a deliverable and returns a verdict.

    This is deliberately *not* the quality gate. The gate is deterministic and
    model-free — governance stays with Hyperium. This reviewer is content-side,
    exactly like generation: it reads the finished deliverable and decides, as a
    human reviewer would, whether it is good enough or what to fix. Its verdict
    drives the same approve / request-changes acts a person performs, so an
    unattended run can iterate without putting a model in charge of the gate.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def review(self, mission: Mission, deliverable: Deliverable) -> ReviewVerdict:
        version = deliverable.latest_version()
        content = version.content if version else ""

        try:
            response = self._llm.generate(self._prompt(mission, deliverable, content))
        except Exception as error:
            logger.warning("Reviewer call failed for '%s': %s", deliverable.key, error)
            return ReviewVerdict(
                False,
                "The review could not be completed; revise for completeness "
                "and clarity, then it will be reviewed again.",
            )

        return self._parse(response)

    def _prompt(self, mission: Mission, deliverable: Deliverable, content: str) -> str:
        sections = ", ".join(deliverable.sections) if deliverable.sections else ""

        return "\n".join(
            part
            for part in [
                "You are a demanding senior quality reviewer at a consultancy. "
                "Judge whether the deliverable below is a satisfactory "
                "professional deliverable for this engagement: complete, "
                "coherent, specific, on-topic and genuinely useful. Reject "
                "vague, thin, generic or incomplete work.",
                "",
                "# Engagement objective",
                mission.objective.description,
                "",
                f"# Deliverable: {deliverable.name}",
                deliverable.description or "",
                (f"Expected to cover: {sections}" if sections else ""),
                "",
                "# Content under review",
                content or "(empty)",
                "",
                "# Your verdict",
                "Respond with a single JSON object and nothing else:",
                '{"approved": true or false, "feedback": "if approved, one '
                'short note; if not, the specific, actionable changes needed"}',
            ]
            if part is not None
        )

    def _parse(self, response: str) -> ReviewVerdict:
        text = _THINK_BLOCK.sub("", response or "").strip()
        match = _JSON_OBJECT.search(text)

        if match is None:
            return ReviewVerdict(
                False,
                "The review was not returned in a usable form; revise for "
                "clarity and completeness.",
            )

        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return ReviewVerdict(
                False,
                "The review was not returned in a usable form; revise for "
                "clarity and completeness.",
            )

        approved = bool(payload.get("approved"))
        feedback = str(payload.get("feedback", "")).strip()

        if not approved and not feedback:
            feedback = (
                "Rejected without detail; improve completeness, structure and "
                "specificity."
            )

        return ReviewVerdict(approved, feedback)
