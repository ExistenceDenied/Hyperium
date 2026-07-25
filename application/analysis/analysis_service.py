from core.analysis.analysis_result import AnalysisResult
from core.analysis.mission_analysis_service import MissionAnalysisService
from core.missions.mission import Mission


class AnalysisService:
    """
    Application service orchestrating mission analysis.
    """

    def __init__(self, mission_analysis_service: MissionAnalysisService) -> None:
        self._mission_analysis_service = mission_analysis_service

    def analyze(self, mission: Mission) -> AnalysisResult:
        return self._mission_analysis_service.analyze(mission)