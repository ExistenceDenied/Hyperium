from core.analysis.analysis_result import AnalysisResult


class AnalysisResultParser:
    """
    Parses an LLM response into an AnalysisResult.

    Temporary implementation for the MVP.
    """

    def parse(self, response: str) -> AnalysisResult:
        return AnalysisResult(
            summary=response.strip(),
        )