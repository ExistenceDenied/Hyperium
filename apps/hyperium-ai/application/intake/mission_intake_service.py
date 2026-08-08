from application.analysis.analysis_service import AnalysisService
from core.analysis.analysis_result import AnalysisResult
from core.missions.mission import Mission


class MissionIntakeService:
    """
    Handles the intake of a new mission.

    The intake process validates and analyses a mission before it
    becomes a project.
    """

    def __init__(self, analysis_service: AnalysisService) -> None:
        self._analysis_service = analysis_service

    def intake(self, mission: Mission) -> AnalysisResult:
        return self._analysis_service.analyze(mission)