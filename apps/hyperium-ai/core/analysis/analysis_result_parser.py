from __future__ import annotations

import json
import re
from typing import Any

from core.analysis.analysis_result import AnalysisResult


class AnalysisParseError(ValueError):
    """
    Raised when an LLM response cannot be turned into a usable AnalysisResult.

    Parsing fails loudly on purpose. A silently empty analysis produces an
    engagement that reports success while understanding nothing.
    """


_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class AnalysisResultParser:
    """
    Parses an LLM response into an AnalysisResult.

    The response is expected to follow the schema in AnalysisPromptBuilder.
    Models routinely wrap that JSON in prose, markdown fences or reasoning
    blocks, so the payload is extracted before decoding.
    """

    def __init__(self, valid_methodologies: list[str] | None = None) -> None:
        self._valid = (
            {key.strip().lower() for key in valid_methodologies}
            if valid_methodologies
            else None
        )

    def parse(self, response: str) -> AnalysisResult:
        payload = self._decode(response)

        summary = str(payload.get("summary", "")).strip()

        if not summary:
            raise AnalysisParseError(
                "Analysis response is missing a 'summary'."
            )

        return AnalysisResult(
            summary=summary,
            assumptions=self._string_list(payload, "assumptions"),
            risks=self._string_list(payload, "risks"),
            recommended_methodology=self._methodology(payload),
            rationale=str(payload.get("rationale", "")).strip(),
        )

    def _methodology(self, payload: dict[str, Any]) -> str | None:
        raw = payload.get("recommended_methodology")

        if not isinstance(raw, str) or not raw.strip():
            return None

        key = raw.strip().lower()

        if self._valid is not None and key not in self._valid:
            raise AnalysisParseError(
                f"Analysis recommended unknown methodology '{raw}'. "
                f"Valid: {', '.join(sorted(self._valid))}."
            )

        return key

    def _decode(self, response: str) -> dict[str, Any]:
        text = _THINK_BLOCK.sub("", response or "").strip()
        match = _JSON_OBJECT.search(text)

        if match is None:
            raise AnalysisParseError(
                "Analysis response contains no JSON object."
            )

        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as error:
            raise AnalysisParseError(
                f"Analysis response is not valid JSON: {error}"
            ) from error

        if not isinstance(payload, dict):
            raise AnalysisParseError(
                "Analysis response must be a JSON object, "
                f"got {type(payload).__name__}."
            )

        return payload

    def _string_list(self, payload: dict[str, Any], field: str) -> list[str]:
        values = payload.get(field, [])

        if not isinstance(values, list):
            return []

        return [item.strip() for item in values if isinstance(item, str)]
