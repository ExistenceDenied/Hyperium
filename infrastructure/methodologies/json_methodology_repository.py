from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from core.methodologies.methodology import (
    ActivityTemplate,
    DeliverableTemplate,
    Methodology,
    MethodologyError,
    Stage,
)
from core.methodologies.quality_gate import QualityGate
from core.methodologies.technique import Technique

logger = logging.getLogger(__name__)

BUILTIN_ROOT = Path(__file__).resolve().parent.parent.parent / "methodologies"


class MethodologyNotFoundError(KeyError):
    """
    Raised when a methodology key does not exist in the registry.
    """


class JsonMethodologyRepository:
    """
    Loads methodologies and techniques from JSON.

    JSON rather than code so that a methodology can be authored, reviewed and
    versioned without touching the runtime — the extensibility rule in
    09-extensibility.md. JSON rather than YAML so that authoring a methodology
    does not add a parser dependency to the platform.

    Every methodology is validated on load. An unusable methodology fails
    immediately and by name, rather than halfway through an engagement.
    """

    def __init__(self, roots: list[Path] | None = None) -> None:
        self._roots = [Path(root) for root in (roots or [BUILTIN_ROOT])]
        self._methodologies: dict[str, Methodology] | None = None
        self._techniques: dict[str, Technique] | None = None

    # ------------------------------------------------------- methodologies

    def all(self) -> list[Methodology]:
        self._load()

        return sorted(self._methodologies.values(), key=lambda item: item.name)

    def get(self, key: str) -> Methodology:
        self._load()

        normalised = key.strip().lower()

        if normalised not in self._methodologies:
            known = ", ".join(sorted(self._methodologies)) or "none"
            raise MethodologyNotFoundError(
                f"No methodology '{key}'. Available: {known}."
            )

        return self._methodologies[normalised]

    def keys(self) -> list[str]:
        self._load()

        return sorted(self._methodologies)

    # ----------------------------------------------------------- techniques

    def techniques(self) -> list[Technique]:
        self._load()

        return sorted(self._techniques.values(), key=lambda item: item.name)

    def technique(self, key: str) -> Technique | None:
        self._load()

        return self._techniques.get(key.strip().lower())

    # -------------------------------------------------------------- loading

    def _load(self) -> None:
        if self._methodologies is not None:
            return

        self._methodologies = {}
        self._techniques = {}

        for root in self._roots:
            self._load_techniques(root / "techniques")
            self._load_methodologies(root)

    def _load_techniques(self, directory: Path) -> None:
        if not directory.exists():
            return

        for path in sorted(directory.glob("*.json")):
            payload = self._read(path)

            technique = Technique(
                key=str(payload["key"]).strip().lower(),
                name=payload["name"],
                description=payload.get("description", ""),
                guidance=payload.get("guidance", ""),
                capabilities=frozenset(
                    str(item).strip().upper()
                    for item in payload.get("capabilities", [])
                ),
            )

            self._techniques[technique.key] = technique

    def _load_methodologies(self, directory: Path) -> None:
        if not directory.exists():
            return

        for path in sorted(directory.glob("*.json")):
            methodology = self._methodology(self._read(path), path)

            try:
                methodology.validate()
            except MethodologyError as error:
                raise MethodologyError(f"{path.name}: {error}") from error

            self._reject_unknown_techniques(methodology, path)
            self._methodologies[methodology.key] = methodology

            logger.debug("Loaded methodology '%s'.", methodology.key)

    def _read(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise MethodologyError(f"{path.name} is not valid JSON: {error}") from error

        if not isinstance(payload, dict):
            raise MethodologyError(f"{path.name} must contain a JSON object.")

        for required in ("key", "name"):
            if not payload.get(required):
                raise MethodologyError(f"{path.name} is missing '{required}'.")

        return payload

    def _methodology(self, payload: dict[str, Any], path: Path) -> Methodology:
        return Methodology(
            key=str(payload["key"]).strip().lower(),
            name=payload["name"],
            description=payload.get("description", ""),
            version=str(payload.get("version", "1.0")),
            discipline=payload.get("discipline", ""),
            principles=tuple(payload.get("principles", [])),
            stages=tuple(
                self._stage(entry, path) for entry in payload.get("stages", [])
            ),
        )

    def _stage(self, payload: dict[str, Any], path: Path) -> Stage:
        gate = payload.get("quality_gate")

        return Stage(
            key=str(payload.get("key", "")).strip(),
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            depends_on=tuple(payload.get("depends_on", [])),
            deliverables=tuple(
                self._deliverable(entry) for entry in payload.get("deliverables", [])
            ),
            quality_gate=self._gate(gate) if gate else None,
        )

    def _gate(self, payload: dict[str, Any]) -> QualityGate:
        return QualityGate(
            description=payload.get("description", ""),
            require_approval=payload.get("require_approval", True),
            minimum_words=int(payload.get("minimum_words", 0)),
            required_sections=tuple(payload.get("required_sections", [])),
        )

    def _deliverable(self, payload: dict[str, Any]) -> DeliverableTemplate:
        return DeliverableTemplate(
            key=str(payload.get("key", "")).strip(),
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            sections=tuple(payload.get("sections", [])),
            activities=tuple(
                self._activity(entry) for entry in payload.get("activities", [])
            ),
        )

    def _activity(self, payload: dict[str, Any]) -> ActivityTemplate:
        return ActivityTemplate(
            key=str(payload.get("key", "")).strip(),
            name=payload.get("name", ""),
            description=payload.get("description", ""),
            capabilities=tuple(
                str(item).strip().upper()
                for item in payload.get("capabilities", [])
            ),
            technique=(
                str(payload["technique"]).strip().lower()
                if payload.get("technique")
                else None
            ),
            depends_on=tuple(payload.get("depends_on", [])),
        )

    def _reject_unknown_techniques(
        self,
        methodology: Methodology,
        path: Path,
    ) -> None:
        for activity in methodology.activities:
            if activity.technique and activity.technique not in self._techniques:
                known = ", ".join(sorted(self._techniques)) or "none"
                raise MethodologyError(
                    f"{path.name}: activity '{activity.key}' references "
                    f"unknown technique '{activity.technique}'. "
                    f"Available: {known}."
                )
