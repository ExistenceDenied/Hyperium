from core.analysis.analysis_prompt_builder import AnalysisPromptBuilder
from core.analysis.analysis_result import AnalysisResult
from core.analysis.analysis_result_parser import AnalysisResultParser
from core.interfaces.llm_provider import LLMProvider
from core.missions.mission import Mission


class MissionAnalysisService:
    """
    Analyzes a mission and produces a structured AnalysisResult.
    """

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm
        self._prompt_builder = AnalysisPromptBuilder()
        self._parser = AnalysisResultParser()

    def analyze(self, mission: Mission) -> AnalysisResult:
        prompt = self._prompt_builder.build(mission)
        response = self._llm.generate(prompt)
        return self._parser.parse(response)