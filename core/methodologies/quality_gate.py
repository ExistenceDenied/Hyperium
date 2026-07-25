from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORDS = re.compile(r"\b\w+\b")


@dataclass(frozen=True)
class DeliverableState:
    """
    The facts a gate needs about one deliverable.

    A gate evaluates *state*, not a Deliverable. Depending on the execution
    package would make methodologies and execution mutually dependent, and
    neither could then be understood or tested on its own.
    """

    key: str
    approved: bool
    status: str = ""
    content: str | None = None


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

    def evaluate(self, states: list[DeliverableState]) -> GateResult:
        failures: list[str] = []

        if not states:
            return GateResult(False, ("The stage produced no deliverables.",))

        for state in states:
            failures.extend(self._check(state))

        return GateResult(not failures, tuple(failures))

    def _check(self, state: DeliverableState) -> list[str]:
        failures: list[str] = []

        if state.content is None:
            return [f"'{state.key}' has no content yet."]

        if self.require_approval and not state.approved:
            failures.append(
                f"'{state.key}' has not been approved"
                + (f" (currently {state.status})." if state.status else ".")
            )

        if self.minimum_words:
            words = len(_WORDS.findall(state.content))

            if words < self.minimum_words:
                failures.append(
                    f"'{state.key}' has {words} words; the gate "
                    f"requires at least {self.minimum_words}."
                )

        lowered = state.content.lower()

        for section in self.required_sections:
            if section.lower() not in lowered:
                failures.append(
                    f"'{state.key}' is missing the required section "
                    f"'{section}'."
                )

        return failures
