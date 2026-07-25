from __future__ import annotations

from dataclasses import dataclass, field

from core.methodologies.quality_gate import QualityGate


@dataclass
class StagePlan:
    """
    A stage as it exists inside a planned engagement.

    The plan carries its own copy of the stage ordering and quality gate
    rather than looking them up in the methodology registry at execution
    time. That matters: a methodology is authored data that can be renamed,
    edited or deleted, and an engagement already in flight must not have its
    governance silently changed — or silently removed — underneath it.

    The methodology that produced the plan is recorded by key, for provenance.
    """

    key: str
    name: str = ""
    depends_on: tuple[str, ...] = ()
    quality_gate: QualityGate | None = field(default=None)
