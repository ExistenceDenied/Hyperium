from __future__ import annotations

from dataclasses import dataclass, field

from core.execution.deliverable import Deliverable


@dataclass
class AnalysisResult:
    """
    Represents the outcome of a mission analysis.
    """

    summary: str = ""
    assumptions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    deliverables: list[Deliverable] = field(default_factory=list)

    def add_deliverable(self, deliverable: Deliverable) -> None:
        if deliverable not in self.deliverables:
            self.deliverables.append(deliverable)