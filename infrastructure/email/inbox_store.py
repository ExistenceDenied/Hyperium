from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from infrastructure.json_store import write_json_atomic


class InboxStore:
    """
    The inbox worker's settings and memory, in one JSON file.

    Holds whether the worker is on, which folder it watches, and a log of the
    messages it has already drafted a reply to — so it acts once per message and
    the log can be shown on the Email page.
    """

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        return bool(self._read().get("enabled", False))

    @property
    def folder(self) -> str:
        return self._read().get("folder", "Inbox")

    @property
    def interval_minutes(self) -> int:
        """How often the worker checks the folder. At least once a minute."""
        return max(1, int(self._read().get("interval_minutes", 2)))

    @property
    def last_seen(self) -> datetime | None:
        """The newest message handled — so a tick only fetches what is newer."""
        value = self._read().get("last_seen")
        return datetime.fromisoformat(value) if value else None

    def set_last_seen(self, at: datetime) -> None:
        with self._lock:
            data = self._read()
            data["last_seen"] = at.isoformat()
            self._write(data)

    def configure(
        self, enabled: bool, folder: str, interval_minutes: int = 2
    ) -> None:
        with self._lock:
            data = self._read()
            data["enabled"] = bool(enabled)
            data["folder"] = (folder or "Inbox").strip() or "Inbox"
            try:
                minutes = int(interval_minutes)
            except (TypeError, ValueError):
                minutes = 2
            data["interval_minutes"] = max(1, minutes)
            self._write(data)

    def is_handled(self, message_id: str) -> bool:
        return any(item["id"] == message_id for item in self._read().get("handled", []))

    def mark_handled(
        self,
        message_id: str,
        sender: str,
        subject: str,
        category: str = "",
        summary: str = "",
        actions: list[str] | None = None,
    ) -> None:
        with self._lock:
            data = self._read()
            handled = data.setdefault("handled", [])
            if any(item["id"] == message_id for item in handled):
                return
            handled.insert(
                0,
                {
                    "id": message_id,
                    "sender": sender,
                    "subject": subject,
                    "category": category,
                    "summary": summary,
                    "actions": list(actions or []),
                    "at": datetime.now(timezone.utc).isoformat(),
                },
            )
            data["handled"] = handled[:200]
            self._write(data)

    def handled(self) -> list[dict]:
        return list(self._read().get("handled", []))

    # --------------------------------------------------------- internals

    def _read(self) -> dict:
        if not self._path.is_file():
            return {}
        return json.loads(self._path.read_text(encoding="utf-8"))

    def _write(self, data: dict) -> None:
        write_json_atomic(self._path, data)
