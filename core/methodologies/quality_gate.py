from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.execution.deliverable import Deliverable

_WORDS = re.compile(r"\b\w+\b")


@dataclass(frozen=True)
class GateResult:
    """
    The outcome of evaluating a stage's quality gate.

    Failures are returned rather than raised: a gate that has not yet passed is
    a normal state of an engagement in flight, not an error.
    """

    passed: bool
    failures: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.passed


@dataclass(frozen=True)
class QualityGate:
    """
    The condition a stage must satisfy before the next stage may begin.

    Gates are declarative and checkable. An LLM never decides whether a gate
    has passed — that would put the model in charge of governance, which
    05-agents.md reserves for Hyperium itself.
    """

    description: str = ""
    require_approval: bool = True
    minimum_words: int = 0
    required_sections: tuple[str, ...] = field(default_factory=tuple)

    def evaluate(self, deliverables: list[Deliverable]) -> GateResult:
        failures: list[str] = []

        if not deliverables:
            return GateResult(False, ("The stage produced no deliverables.",))

        for deliverable in deliverables:
            failures.extend(self._check(deliverable))

        return GateResult(not failures, tuple(failures))

    def _check(self, deliverable: Deliverable) -> list[str]:
        failures: list[str] = []
        version = deliverable.latest_version()

        if version is None:
            return [f"'{deliverable.key}' has no content yet."]

        if self.require_approval and not deliverable.is_approved:
            failures.append(
                f"'{deliverable.key}' has not been approved "
                f"(currently {deliverable.status.value})."
            )

        if self.minimum_words:
            words = len(_WORDS.findall(version.content))

            if words < self.minimum_words:
                failures.append(
                    f"'{deliverable.key}' has {words} words; the gate "
                    f"requires at least {self.minimum_words}."
                )

        lowered = version.content.lower()

        for section in self.required_sections:
            if section.lower() not in lowered:
                failures.append(
                    f"'{deliverable.key}' is missing the required section "
                    f"'{section}'."
                )

        return failures
