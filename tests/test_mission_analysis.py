from core.analysis.analysis_result import AnalysisResult
from core.analysis.mission_analysis_service import MissionAnalysisService
from core.missions.mission import Mission
from core.missions.objective import Objective
from core.missions.success_criterion import SuccessCriterion


class FakeLLMService:
    def ask_json(self, prompt: str) -> dict:
        return {
            "domain": "Professional Services",
            "goal": "Create PSBOK",
            "disciplines": [
                "Business Analysis",
                "Instructional Design",
            ],
            "deliverables": [
                "Body of Knowledge",
                "Training Material",
            ],
            "assumptions": [],
            "risks": [],
            "summary": "Mission analysed successfully.",
        }


def test_mission_can_be_analysed():
    mission = Mission(
        title="Create PSBOK",
        objective=Objective(
            description="Create the first Professional Services Body of Knowledge."
        ),
    )

    mission.add_success_criterion(
        SuccessCriterion(
            description="Version 1.0 is published."
        )
    )

    mission.validate()

    service = MissionAnalysisService(
        llm=FakeLLMService(),
    )

    result = service.analyse(mission)

    assert isinstance(result, AnalysisResult)
    assert result.domain == "Professional Services"
    assert result.goal == "Create PSBOK"
    assert "Business Analysis" in result.disciplines