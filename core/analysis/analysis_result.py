from __future__ import annotations

from dataclasses import dataclass, field

from core.execution.deliverable import Deliverable


@dataclass
class AnalysisResult:
    """
    Represents the outcome of a mission analysis.

    Since 2.0 the deliverables on this object are produced by a methodology
    rather than by the model. The analysis contributes understanding —
    summary, assumptions, risks — and a methodology recommendation.
    """

    summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)
    recommended_methodology: str | None = None
    rationale: str = ""

    def add_deliverable(self, deliverable: Deliverable) -> None:
        if deliverable not in self.deliverables:
            self.deliverables.append(deliverable)
