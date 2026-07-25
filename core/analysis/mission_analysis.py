from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class MissionAnalysis:
    """
    Represents the outcome of analysing a mission.

    MissionAnalysis captures the understanding of the mission before
    any planning decisions are made.
    """

    domain: str | None = None
    goal: str | None = None
    assumptions: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    recommended_disciplines: List[str] = field(default_factory=list)
    recommended_deliverables: List[str] = field(default_factory=list)