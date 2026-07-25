from __future__ import annotations

import logging

from core.analysis.analysis_prompt_builder import AnalysisPromptBuilder
from core.analysis.analysis_result import AnalysisResult
from core.analysis.analysis_result_parser import AnalysisResultParser
from core.interfaces.llm_provider import LLMProvider
from core.missions.mission import Mission

logger = logging.getLogger(__name__)


class MissionAnalysisService:
    """
    Analyzes a mission and produces a structured AnalysisResult.

    Since 2.0 the analysis informs the engagement rather than defining it. If
    the model fails or returns something unusable the engagement still runs,
    because the methodology — not the analysis — determines the work. Before
    2.0 this same failure produced an empty plan and a vacuous success.
    """

    def __init__(
        self,
        llm: LLMProvider,
        methodologies: list | None = None,
    ) -> None:
        self._llm = llm
        self._methodologies = methodologies or []
        self._prompt_builder = AnalysisPromptBuilder()
        self._parser = AnalysisResultParser(
            valid_methodologies=[item.key for item in self._methodologies]
        )

    def analyze(self, mission: Mission) -> AnalysisResult:
        prompt = self._prompt_builder.build(mission, self._methodologies)

        try:
            return self._parser.parse(self._llm.generate(prompt))
        except Exception as error:
            logger.warning(
                "Mission analysis failed for '%s': %s. Continuing without it.",
                mission.title,
                error,
            )

            return AnalysisResult(
                summary="",
                rationale=f"Analysis unavailable: {error}",
            )
