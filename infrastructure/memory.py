from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

from core.memory.memory_entry import MemoryEntry


class MemoryStore:
    """
    The business's durable memory: editable by hand, read into every agent.

    Stored as a single JSON file so the whole memory is one small, portable
    thing. `as_context` renders it into the block prepended to an agent's task,
    so the work reflects what the business is, charges and sounds like without
    being told again each time.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)

    def list(self) -> list[MemoryEntry]:
        return [self._from_dict(item) for item in self._read()]

    def get(self, entry_id: UUID) -> MemoryEntry | None:
        for entry in self.list():
            if entry.id == entry_id:
                return entry
        return None

    def add(self, text: str, category: str = "general") -> MemoryEntry:
        entry = MemoryEntry(text=text.strip(), category=self._norm(category))
        data = self._read()
        data.append(self._to_dict(entry))
        self._write(data)
        return entry

    def update(self, entry_id: UUID, text: str, category: str) -> None:
        data = self._read()
        for item in data:
            if item["id"] == str(entry_id):
                item["text"] = text.strip()
                item["category"] = self._norm(category)
        self._write(data)

    def delete(self, entry_id: UUID) -> None:
        self._write([item for item in self._read() if item["id"] != str(entry_id)])

    def as_context(self) -> str:
        entries = self.list()
        if not entries:
            return ""

        by_category: dict[str, list[str]] = {}
        for entry in entries:
            by_category.setdefault(entry.category, []).append(entry.text)

        lines = [
            "What you know about this business — use it, and do not contradict "
            "it. Where a needed detail is not here, say so rather than inventing "
            "it:"
        ]
        for category in sorted(by_category):
            lines.append(f"\n{category}:")
            lines.extend(f"- {text}" for text in by_category[category])

        return "\n".join(lines)

    # --------------------------------------------------------- internals

    def _norm(self, category: str) -> str:
        return (category or "general").strip().lower() or "general"

    def _read(self) -> list[dict]:
        if not self._path.is_file():
            return []
        return json.loads(self._path.read_text(encoding="utf-8")).get("entries", [])

    def _write(self, entries: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"entries": entries}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _to_dict(self, entry: MemoryEntry) -> dict:
        return {
            "id": str(entry.id),
            "text": entry.text,
            "category": entry.category,
            "created_at": entry.created_at.isoformat(),
        }

    def _from_dict(self, data: dict) -> MemoryEntry:
        return MemoryEntry(
            text=data["text"],
            category=data.get("category", "general"),
            id=UUID(data["id"]),
            created_at=datetime.fromisoformat(data["created_at"]),
        )
