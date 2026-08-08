"""
Mission analysis.

The analysis informs the engagement; it does not define it. The most important
test here is the last one: a failed analysis must not cost the engagement.
"""

from core.analysis.analysis_result import AnalysisResult
from core.analysis.mission_analysis_service import MissionAnalysisService
from core.interfaces.llm_provider import LLMProvider
from core.missions.mission import Mission
from core.missions.objective import Objective
from core.missions.success_criterion import SuccessCriterion
from tests.fixtures import SINGLE_STAGE, TWO_STAGE

RESPONSE = """
{
  "summary": "Mission analysed successfully.",
  "assumptions": ["Subject matter experts are available."],
  "risks": ["Scope may expand beyond one volume."],
  "recommended_methodology": "test-two-stage",
  "rationale": "It is a discovery-then-design engagement."
}
"""


class FakeLLM(LLMProvider):
    def __init__(self, response: str = RESPONSE) -> None:
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


class BrokenLLM(LLMProvider):
    def generate(self, prompt: str) -> str:
        raise ConnectionError("the model is unreachable")


def build_mission() -> Mission:
    mission = Mission(
        title="Create PSBOK",
        objective=Objective(
            description="Create the first Professional Services Body of Knowledge."
        ),
    )
    mission.add_success_criterion(
        SuccessCriterion(description="Version 1.0 is published.")
    )

    return mission


def service(llm=None, methodologies=(TWO_STAGE, SINGLE_STAGE)):
    return MissionAnalysisService(llm or FakeLLM(), methodologies=list(methodologies))


def test_mission_can_be_analyzed():
    mission = build_mission()
    mission.validate()

    result = service().analyze(mission)

    assert isinstance(result, AnalysisResult)
    assert result.summary == "Mission analysed successfully."
    assert result.assumptions == ["Subject matter experts are available."]
    assert result.risks == ["Scope may expand beyond one volume."]
    assert result.recommended_methodology == "test-two-stage"


def test_the_analysis_does_not_produce_a_work_breakdown():
    """2.0's inversion: the methodology owns the work, not the model."""
    result = service().analyze(build_mission())

    # The field does not exist at all — ADR-002 forbids the analysis context
    # from creating execution plans, so it carries no deliverables to create.
    assert not hasattr(result, "deliverables")


def test_the_prompt_offers_the_available_methodologies():
    llm = FakeLLM()

    service(llm).analyze(build_mission())

    prompt = llm.prompts[0]

    assert "test-two-stage" in prompt
    assert "test-single-stage" in prompt
    assert "Do not invent one." in prompt


def test_the_prompt_forbids_planning_the_work():
    llm = FakeLLM()

    service(llm).analyze(build_mission())

    assert "NOT to plan the work" in llm.prompts[0]


def test_a_provider_failure_does_not_raise():
    result = service(BrokenLLM()).analyze(build_mission())

    assert result.summary == ""
    assert "Analysis unavailable" in result.rationale
    assert result.recommended_methodology is None


def test_an_unparsable_response_does_not_raise():
    result = service(FakeLLM("not json at all")).analyze(build_mission())

    assert "Analysis unavailable" in result.rationale
