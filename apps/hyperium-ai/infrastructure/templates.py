from __future__ import annotations

from pathlib import Path

BUILTIN_ROOT = Path(__file__).resolve().parent.parent / "templates"


class TemplateLibrary:
    """
    Loads polished deliverable templates from Markdown, keyed by deliverable.

    A template is the skeleton every deliverable of that key must fill in, so
    two engagements produce the same shape of document and nothing is left to
    the model's improvisation. Convention over configuration: the file
    `templates/<deliverable-key>.md` is the template for that deliverable, and
    its presence alone puts it in front of the agent — no methodology change is
    needed to add or change one.
    """

    def __init__(self, root: Path | None = None) -> None:
        self._root = Path(root) if root else BUILTIN_ROOT
        self._cache: dict[str, str | None] = {}

    def get(self, deliverable_key: str) -> str | None:
        key = (deliverable_key or "").strip()

        if key not in self._cache:
            path = self._root / f"{key}.md"
            text = path.read_text(encoding="utf-8").strip() if path.is_file() else ""
            self._cache[key] = text or None

        return self._cache[key]
