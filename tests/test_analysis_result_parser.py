"""
Analysis parsing.

Since 2.0 the analysis contributes understanding and a methodology
recommendation. It no longer decomposes the mission into work — a methodology
does that — so there is no work breakdown to parse.
"""

import pytest

from core.analysis.analysis_result_parser import (
    AnalysisParseError,
    AnalysisResultParser,
)

VALID = """
{
  "summary": "A one-day training for junior consultants.",
  "assumptions": ["Juniors have no prior BA training."],
  "risks": ["One day may be too short for the scope."],
  "recommended_methodology": "business-analysis",
  "rationale": "The mission is a discovery-then-specification engagement."
}
"""


def parser(valid=("business-analysis", "solution-delivery")):
    return AnalysisResultParser(valid_methodologies=list(valid))


def test_parses_understanding_and_recommendation():
    result = parser().parse(VALID)

    assert result.summary == "A one-day training for junior consultants."
    assert result.assumptions == ["Juniors have no prior BA training."]
    assert result.risks == ["One day may be too short for the scope."]
    assert result.recommended_methodology == "business-analysis"
    assert "discovery-then-specification" in result.rationale


def test_parses_a_response_wrapped_in_a_markdown_fence():
    result = parser().parse(f"Here you go:\n\n```json\n{VALID}\n```\n")

    assert result.recommended_methodology == "business-analysis"


def test_parses_a_response_preceded_by_a_reasoning_block():
    result = parser().parse(f"<think>Let me consider.</think>\n{VALID}")

    assert result.summary


def test_the_methodology_key_is_normalised():
    response = """
    {"summary": "s", "recommended_methodology": "  Business-Analysis  "}
    """

    assert parser().parse(response).recommended_methodology == "business-analysis"


def test_rejects_a_hallucinated_methodology():
    """The model may not invent a methodology that does not exist."""
    response = '{"summary": "s", "recommended_methodology": "vibes-driven"}'

    with pytest.raises(AnalysisParseError, match="vibes-driven"):
        parser().parse(response)


def test_a_missing_recommendation_is_allowed():
    """Planning can still fall back to the mission or the default."""
    result = parser().parse('{"summary": "s"}')

    assert result.recommended_methodology is None


def test_rejects_a_response_that_is_not_json():
    with pytest.raises(AnalysisParseError, match="no JSON object"):
        parser().parse("I am afraid I cannot help with that.")


def test_rejects_malformed_json():
    with pytest.raises(AnalysisParseError, match="not valid JSON"):
        parser().parse('{"summary": [}')


def test_rejects_a_response_without_a_summary():
    with pytest.raises(AnalysisParseError, match="'summary'"):
        parser().parse('{"assumptions": []}')


def test_non_string_list_entries_are_dropped():
    response = '{"summary": "s", "risks": ["real", 42, null]}'

    assert parser().parse(response).risks == ["real"]


def test_a_parser_without_a_whitelist_accepts_any_key():
    result = AnalysisResultParser().parse(
        '{"summary": "s", "recommended_methodology": "anything"}'
    )

    assert result.recommended_methodology == "anything"
