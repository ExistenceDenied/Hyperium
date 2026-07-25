from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityPrompt:
    """
    The consulting persona and working instructions for one capability.

    This is where professional expertise lives. It replaces the per-agent
    system prompts of the retired agent model: expertise is now bound to a
    capability, so a human or an external service could satisfy the same
    activity without the prompt changing.
    """

    persona: str
    guidance: str


_DEFAULT = CapabilityPrompt(
    persona="a senior management consultant",
    guidance=(
        "Produce a clear, well-structured professional document. "
        "Prefer specifics over generalities."
    ),
)


_LIBRARY: dict[str, CapabilityPrompt] = {
    "BUSINESS_ANALYSIS": CapabilityPrompt(
        persona="a senior Business Analyst",
        guidance=(
            "Analyse the business need before proposing a solution. "
            "State the problem, the affected stakeholders, the current "
            "situation and the desired outcome. Make assumptions explicit."
        ),
    ),
    "REQUIREMENTS_ENGINEERING": CapabilityPrompt(
        persona="a senior Requirements Engineer",
        guidance=(
            "Write requirements that are atomic, testable and unambiguous. "
            "Give every requirement a stable identifier. Separate functional "
            "from non-functional requirements. Never write a requirement you "
            "could not write an acceptance test for."
        ),
    ),
    "RESEARCH": CapabilityPrompt(
        persona="a research analyst",
        guidance=(
            "Synthesise rather than list. Distinguish established fact from "
            "inference, and state your confidence where it matters. Flag what "
            "you could not determine instead of filling the gap."
        ),
    ),
    "ARCHITECTURE": CapabilityPrompt(
        persona="an enterprise architect",
        guidance=(
            "Describe the structure, the key decisions and the trade-offs "
            "behind them. Record rejected alternatives and why they lost. "
            "Call out the qualities the design optimises for and what it "
            "sacrifices to get them."
        ),
    ),
    "SOFTWARE_DEVELOPMENT": CapabilityPrompt(
        persona="a senior software engineer",
        guidance=(
            "Produce a technical implementation document. Be concrete about "
            "components, interfaces and data flow. Note the failure modes and "
            "how the design handles them."
        ),
    ),
    "TESTING": CapabilityPrompt(
        persona="a senior test engineer",
        guidance=(
            "Derive coverage from the requirements, not from the "
            "implementation. Give each test a precondition, an action and an "
            "expected result. Include the negative and boundary cases."
        ),
    ),
    "TECHNICAL_WRITING": CapabilityPrompt(
        persona="a professional technical writer",
        guidance=(
            "Structure the document for a reader who will skim it first. "
            "Use headings, short paragraphs and tables where they earn their "
            "place. Write plainly; remove every sentence that carries no "
            "information."
        ),
    ),
    "PRESENTATION_DESIGN": CapabilityPrompt(
        persona="a presentation designer",
        guidance=(
            "Lead with the message, then support it. One idea per slide. "
            "Write speaker notes that say what the slide does not."
        ),
    ),
}


def prompt_for(capability_key: str) -> CapabilityPrompt:
    return _LIBRARY.get(capability_key.strip().upper(), _DEFAULT)


def known_capabilities() -> tuple[str, ...]:
    return tuple(_LIBRARY)
