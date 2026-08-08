from __future__ import annotations

import json
from pathlib import Path

from core.capabilities.capability_catalog import CapabilityCatalog
from core.methodologies.technique import Technique


class TechniqueRepository:
    """
    Full CRUD over the technique library, plus each technique's template file.

    Techniques are authored JSON in `methodologies/techniques/`; their templates
    are Markdown files under `techniques/templates/<key>.md`, downloadable and
    uploadable so a consultant can shape a technique's output to their own
    house style. Capabilities are validated on save against the catalogue, so a
    technique can never reference a capability that does not exist.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._templates = self._root / "templates"

    def list(self) -> list[Technique]:
        if not self._root.is_dir():
            return []
        techniques = [self._load(path) for path in self._root.glob("*.json")]
        return sorted(techniques, key=lambda technique: technique.name)

    def get(self, key: str) -> Technique | None:
        path = self._json_path(key)
        return self._load(path) if path.is_file() else None

    def save(self, technique: Technique) -> None:
        if not technique.key.strip():
            raise ValueError("A technique needs a key.")

        self._reject_unknown_capabilities(technique.capabilities)

        self._root.mkdir(parents=True, exist_ok=True)
        payload = {
            "key": self._norm(technique.key),
            "name": technique.name,
            "description": technique.description,
            "capabilities": sorted(technique.capabilities),
            "guidance": technique.guidance,
        }
        self._json_path(technique.key).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def delete(self, key: str) -> None:
        path = self._json_path(key)
        if path.is_file():
            path.unlink()
        self.delete_template(key)

    # --------------------------------------------------------- templates

    def template_bytes(self, key: str) -> bytes | None:
        path = self._template_path(key)
        return path.read_bytes() if path.is_file() else None

    def has_template(self, key: str) -> bool:
        return self._template_path(key).is_file()

    def save_template(self, key: str, content: bytes) -> None:
        self._templates.mkdir(parents=True, exist_ok=True)
        self._template_path(key).write_bytes(content)

    def delete_template(self, key: str) -> None:
        path = self._template_path(key)
        if path.is_file():
            path.unlink()

    def _template_text(self, key: str) -> str:
        path = self._template_path(key)
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    # --------------------------------------------------------- internals

    def _reject_unknown_capabilities(self, capabilities) -> None:
        known = set(CapabilityCatalog.keys())
        unknown = {c for c in capabilities if c not in known}
        if unknown:
            raise ValueError(
                f"Unknown capabilities: {', '.join(sorted(unknown))}. "
                f"Valid: {', '.join(sorted(known))}."
            )

    def _load(self, path: Path) -> Technique:
        data = json.loads(path.read_text(encoding="utf-8"))
        key = self._norm(data.get("key", ""))
        return Technique(
            key=key,
            name=data.get("name", ""),
            description=data.get("description", ""),
            guidance=data.get("guidance", ""),
            capabilities=frozenset(
                str(c).strip().upper() for c in data.get("capabilities", [])
            ),
            template=self._template_text(key),
        )

    def _norm(self, key: str) -> str:
        return str(key).strip().lower()

    def _json_path(self, key: str) -> Path:
        return self._root / f"{self._norm(key)}.json"

    def _template_path(self, key: str) -> Path:
        return self._templates / f"{self._norm(key)}.md"
