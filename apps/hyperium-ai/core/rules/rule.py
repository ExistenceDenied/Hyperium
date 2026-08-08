from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID, uuid4

# The operators a condition may use — deliberately small and DMN-like, so a
# rule reads plainly and never needs a model to evaluate. String operators are
# case-insensitive, and a comma-separated value means "any of" (as a DMN cell
# lists alternatives): sender startsWith "kris.leunis, krisleunis".
OPERATORS = (
    "any", "equals", "notEquals", "startsWith", "contains", "in", "matches",
    "gte", "lte",
)


def _alts(value: str) -> list[str]:
    return [part.strip() for part in str(value).split(",") if part.strip()]


@dataclass
class Condition:
    """One test against a named input, e.g. sender startsWith 'kris.leunis'."""

    input: str
    op: str = "any"
    value: str = ""

    def test(self, inputs: dict) -> bool:
        if self.op == "any":
            return True

        actual = str(inputs.get(self.input, "")).strip()
        low = actual.lower()

        if self.op == "equals":
            return any(low == a.lower() for a in _alts(self.value))
        if self.op == "notEquals":
            return all(low != a.lower() for a in _alts(self.value))
        if self.op == "startsWith":
            return any(low.startswith(a.lower()) for a in _alts(self.value))
        if self.op == "contains":
            return any(a.lower() in low for a in _alts(self.value))
        if self.op == "in":
            return low in [a.lower() for a in _alts(self.value)]
        if self.op == "matches":
            try:
                return re.search(self.value, actual, re.IGNORECASE) is not None
            except re.error:
                return False
        if self.op in ("gte", "lte"):
            try:
                left, right = float(actual), float(self.value)
            except (TypeError, ValueError):
                return False
            return left >= right if self.op == "gte" else left <= right

        return False


@dataclass
class Rule:
    """
    A row of a decision table: when all conditions hold, apply the outputs.

    Conditions are ANDed (a DMN rule row); an OR is expressed either as two rules
    or a comma-separated value in one condition. Outputs are named assignments,
    e.g. {"delivery": "send", "attach_deliverables": "true"}.
    """

    name: str
    conditions: list[Condition] = field(default_factory=list)
    outputs: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    id: UUID = field(default_factory=uuid4)

    def matches(self, inputs: dict) -> bool:
        return self.enabled and all(c.test(inputs) for c in self.conditions)


@dataclass
class Decision:
    """What the table decided, and which rules produced it — the audit trail."""

    outputs: dict[str, str] = field(default_factory=dict)
    fired: list[str] = field(default_factory=list)

    def get(self, key: str, default: str = "") -> str:
        return self.outputs.get(key, default)

    def is_true(self, key: str) -> bool:
        return self.get(key).strip().lower() in ("true", "yes", "1")


class RuleSet:
    """
    An ordered decision table evaluated deterministically.

    Hit policy: rules are tried in order and each matching rule contributes its
    outputs, but an output already set by an earlier rule wins (first-write-wins
    per key). So a specific rule near the top overrides a general default below
    it, and every fired rule is recorded so a decision can always be explained.
    """

    def __init__(self, rules: list[Rule]) -> None:
        self._rules = list(rules)

    def decide(self, inputs: dict) -> Decision:
        outputs: dict[str, str] = {}
        fired: list[str] = []
        for rule in self._rules:
            if not rule.matches(inputs):
                continue
            fired.append(rule.name)
            for key, val in rule.outputs.items():
                outputs.setdefault(key, val)
        return Decision(outputs=outputs, fired=fired)
