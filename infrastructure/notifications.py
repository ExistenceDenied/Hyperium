from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from uuid import UUID

from core.notifications.notification import Notification

_MAX = 200  # keep the feed bounded; the oldest fall off


class NotificationStore:
    """
    The alert feed, in one JSON file, newest first.

    Written from background threads (a task finishing, an agent asking to act)
    and read by the page and the poll endpoint, so every access takes a lock.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    def add(self, kind: str, text: str, link: str = "") -> Notification:
        note = Notification(kind=kind, text=text, link=link)
        with self._lock:
            data = self._read()
            data.insert(0, self._to_dict(note))
            self._write(data[:_MAX])
        return note

    def list(self, limit: int = 50) -> list[Notification]:
        with self._lock:
            return [self._from_dict(item) for item in self._read()[:limit]]

    def unread(self, limit: int = 50) -> list[Notification]:
        return [note for note in self.list(limit) if not note.read]

    def unread_count(self) -> int:
        with self._lock:
            return sum(1 for item in self._read() if not item.get("read"))

    def mark_read(self, note_id: UUID) -> None:
        with self._lock:
            data = self._read()
            for item in data:
                if item["id"] == str(note_id):
                    item["read"] = True
            self._write(data)

    def mark_all_read(self) -> None:
        with self._lock:
            data = self._read()
            for item in data:
                item["read"] = True
            self._write(data)

    # --------------------------------------------------------- internals

    def _read(self) -> list[dict]:
        if not self._path.is_file():
            return []
        return json.loads(self._path.read_text(encoding="utf-8")).get("items", [])

    def _write(self, items: list[dict]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"items": items}, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _to_dict(self, note: Notification) -> dict:
        return {
            "id": str(note.id),
            "text": note.text,
            "kind": note.kind,
            "link": note.link,
            "read": note.read,
            "at": note.at.isoformat(),
        }

    def _from_dict(self, data: dict) -> Notification:
        return Notification(
            text=data["text"],
            id=UUID(data["id"]),
            kind=data.get("kind", "task"),
            link=data.get("link", ""),
            read=data.get("read", False),
            at=datetime.fromisoformat(data["at"]),
        )
