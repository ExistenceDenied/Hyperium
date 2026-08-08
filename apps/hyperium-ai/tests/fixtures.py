"""
Shared test fixtures.

Tests use a methodology defined here rather than the authored ones under
`methodologies/`. Built-in methodologies are content and will change; the
behaviour of the engine must not move when they do.
"""

from __future__ import annotations

from core.capabilities.capability_catalog import CapabilityCatalog
from core.capabilities.proficiency_level import ProficiencyLevel
from core.interfaces.llm_provider import LLMProvider
from core.methodologies.methodology import (
    ActivityTemplate,
    DeliverableTemplate,
    Methodology,
    Stage,
)
from core.methodologies.quality_gate import QualityGate
from core.methodologies.technique import Technique
from core.missions.mission import Mission
from core.missions.objective import Objective
from core.missions.success_criterion import SuccessCriterion
from core.resources.ai_resource import AIResource

# Two stages, one deliverable each, with a gate between them. This is the
# smallest shape that exercises stage ordering and the approval gate.
TWO_STAGE = Methodology(
    key="test-two-stage",
    name="Two Stage Test Methodology",
    description="Discovery then design.",
    discipline="Testing",
    stages=(
        Stage(
            key="discovery",
            name="Discovery",
            quality_gate=QualityGate(
                description="Requirements are agreed.",
                require_approval=True,
            ),
            deliverables=(
                DeliverableTemplate(
                    key="requirements",
                    name="Training Requirements",
                    sections=("Learning needs", "Constraints"),
                    activities=(
                        ActivityTemplate(
                            key="elicit",
                            name="Elicit learning needs",
                            description="Determine what juniors must do.",
                            capabilities=("BUSINESS_ANALYSIS",),
                            technique="interviewing",
                        ),
                    ),
                ),
            ),
        ),
        Stage(
            key="design",
            name="Design",
            depends_on=("discovery",),
            deliverables=(
                DeliverableTemplate(
                    key="curriculum",
                    name="Training Curriculum",
                    activities=(
                        ActivityTemplate(
                            key="design-curriculum",
                            name="Design the curriculum",
                            capabilities=("TECHNICAL_WRITING",),
                            depends_on=("elicit",),
                        ),
                    ),
                ),
            ),
        ),
    ),
)

# One stage, one deliverable, two dependent activities — the shape that
# exposed the intra-deliverable deadlock.
SINGLE_STAGE = Methodology(
    key="test-single-stage",
    name="Single Stage Test Methodology",
    stages=(
        Stage(
            key="discovery",
            name="Discovery",
            deliverables=(
                DeliverableTemplate(
                    key="requirements",
                    name="Training Requirements",
                    activities=(
                        ActivityTemplate(
                            key="elicit",
                            name="Elicit learning needs",
                            capabilities=("BUSINESS_ANALYSIS",),
                        ),
                        ActivityTemplate(
                            key="document",
                            name="Document the requirements",
                            capabilities=("TECHNICAL_WRITING",),
                            depends_on=("elicit",),
                        ),
                    ),
                ),
            ),
        ),
    ),
)

INTERVIEWING = Technique(
    key="interviewing",
    name="Stakeholder Interviewing",
    description="Structured conversations with stakeholders.",
    guidance="Ask open questions and record what was said, not what you infer.",
    capabilities=frozenset({"BUSINESS_ANALYSIS"}),
)


class FakeMethodologies:
    """Stands in for JsonMethodologyRepository."""

    def __init__(self, methodologies=None, techniques=None) -> None:
        self._methodologies = {
            item.key: item for item in (methodologies or [TWO_STAGE])
        }
        self._techniques = {
            item.key: item for item in (techniques or [INTERVIEWING])
        }

    def all(self):
        return list(self._methodologies.values())

    def keys(self):
        return sorted(self._methodologies)

    def get(self, key: str):
        normalised = (key or "").strip().lower()

        if normalised not in self._methodologies:
            raise KeyError(f"No methodology '{key}'.")

        return self._methodologies[normalised]

    def techniques(self):
        return list(self._techniques.values())

    def technique(self, key: str):
        return self._techniques.get((key or "").strip().lower())


ANALYSIS_RESPONSE = """
{
  "summary": "A one-day training built on a requirements baseline.",
  "assumptions": ["Juniors have no prior BA training."],
  "risks": ["One day may be too short."],
  "recommended_methodology": "test-two-stage",
  "rationale": "The mission is a discovery-then-design engagement."
}
"""


class ScriptedLLM(LLMProvider):
    """
    Returns the analysis first, then marked content per activity.

    Since 2.0 the analysis no longer carries the work breakdown, so this only
    has to supply understanding and a methodology recommendation.
    """

    def __init__(self, analysis: str = ANALYSIS_RESPONSE) -> None:
        self.analysis = analysis
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)

        if "Engagement Analyst" in prompt:
            return self.analysis

        if "Design the curriculum" in prompt:
            return "## Curriculum\nDay one covers elicitation."

        if "Document the requirements" in prompt:
            return "## Documented requirements\nWritten up from the workshop."

        return "## Learning needs\nJuniors must run an intake workshop."


def build_mission(methodology: str | None = None) -> Mission:
    mission = Mission(
        title="Create a Business Analysis training",
        objective=Objective(
            description="Develop a one-day training for junior consultants.",
        ),
        methodology=methodology,
    )
    mission.add_success_criterion(
        SuccessCriterion(description="Juniors can run an intake workshop.")
    )

    return mission


def build_consultant(name: str = "Claude") -> AIResource:
    consultant = AIResource(
        name=name,
        provider="Anthropic",
        model="claude-opus-4",
    )

    for key in CapabilityCatalog.keys():
        consultant.add_capability(
            CapabilityCatalog.get(key),
            ProficiencyLevel.ADVANCED,
        )

    return consultant
