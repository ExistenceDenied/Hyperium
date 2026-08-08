from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AnalysisResult:
    """
    Represents the outcome of a mission analysis.

    The analysis contributes understanding — summary, assumptions, risks — and
    a methodology recommendation. It deliberately carries no deliverables:
    since 2.0 a methodology decides the work, and ADR-002 forbids the analysis
    context from creating execution plans.
    """

    summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    recommended_methodology: str | None = None
    rationale: str = ""
