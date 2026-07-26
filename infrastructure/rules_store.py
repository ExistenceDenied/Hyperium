from __future__ import annotations

import json
import threading
from pathlib import Path
from uuid import UUID

from core.rules.rule import Condition, Rule, RuleSet


class RuleStore:
    """
    The business rules, held as a decision table in one JSON file.

    Editable by hand or in the UI, and loaded into a RuleSet the email worker
    consults. Also holds the outbound kill-switch: a single flag that forces
    every reply back to a draft regardless of what any rule says.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def rule_set(self) -> RuleSet:
        return RuleSet([self._from_dict(item) for item in self._read_rules()])

    def list(self) -> list[Rule]:
        return [self._from_dict(item) for item in self._read_rules()]

    def add(
        self,
        name: str,
        conditions: list[Condition],
        outputs: dict[str, str],
    ) -> Rule:
        rule = Rule(name=name.strip(), conditions=conditions, outputs=outputs)
        with self._lock:
            data = self._read()
            data.setdefault("rules", []).append(self._to_dict(rule))
            self._write(data)
        return rule

    def delete(self, rule_id: UUID) -> None:
        with self._lock:
            data = self._read()
            data["rules"] = [
                r for r in data.get("rules", []) if r["id"] != str(rule_id)
            ]
            self._write(data)

    def set_enabled(self, rule_id: UUID, enabled: bool) -> None:
        with self._lock:
            data = self._read()
            for r in data.get("rules", []):
                if r["id"] == str(rule_id):
                    r["enabled"] = bool(enabled)
            self._write(data)

    # --- outbound kill-switch: sending is only ever possible when this is on ---

    @property
    def sending_enabled(self) -> bool:
        return bool(self._read().get("sending_enabled", False))

    def set_sending_enabled(self, enabled: bool) -> None:
        with self._lock:
            data = self._read()
            data["sending_enabled"] = bool(enabled)
            self._write(data)

    # --------------------------------------------------------- internals

    def _read_rules(self) -> list[dict]:
        return self._read().get("rules", [])

    def _read(self) -> dict:
        if not self._path.is_file():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _to_dict(self, rule: Rule) -> dict:
        return {
            "id": str(rule.id),
            "name": rule.name,
            "enabled": rule.enabled,
            "conditions": [
                {"input": c.input, "op": c.op, "value": c.value}
                for c in rule.conditions
            ],
            "outputs": dict(rule.outputs),
        }

    def _from_dict(self, data: dict) -> Rule:
        return Rule(
            name=data["name"],
            id=UUID(data["id"]),
            enabled=data.get("enabled", True),
            conditions=[
                Condition(
                    input=c["input"],
                    op=c.get("op", "any"),
                    value=c.get("value", ""),
                )
                for c in data.get("conditions", [])
            ],
            outputs=dict(data.get("outputs", {})),
        )
