from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.missions.mission import Mission
from core.missions.mission_status import MissionStatus
from infrastructure.persistence.mission_serializer import (
    SCHEMA_VERSION,
    MissionSerializer,
)


class MissionNotFoundError(KeyError):
    """
    Raised when a mission id does not exist in the backlog.
    """


class MissionRepository:
    """
    The mission backlog, stored as one JSON file per mission.

    Ordering is a repository concern rather than a caller concern, so every
    listing comes back in backlog order: most important first, oldest first
    within a priority.
    """

    def __init__(
        self,
        root: Path,
        serializer: MissionSerializer | None = None,
    ) -> None:
        self._root = Path(root)
        self._serializer = serializer or MissionSerializer()

    def save(self, mission: Mission) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)

        path = self._path(mission.id)
        payload = {
            "schema_version": SCHEMA_VERSION,
            **self._serializer.to_dict(mission),
        }

        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return path

    def get(self, mission_id: UUID) -> Mission:
        path = self._path(mission_id)

        if not path.exists():
            raise MissionNotFoundError(f"No mission '{mission_id}' in the backlog.")

        payload = json.loads(path.read_text(encoding="utf-8"))
        version = payload.get("schema_version")

        if version != SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported mission schema version {version!r}; "
                f"expected {SCHEMA_VERSION}."
            )

        return self._serializer.from_dict(payload)

    def list(
        self,
        status: MissionStatus | None = None,
        include_archived: bool = False,
    ) -> list[Mission]:
        missions = [self.get(item) for item in self._ids()]

        if status is not None:
            missions = [item for item in missions if item.status is status]
        elif not include_archived:
            missions = [
                item
                for item in missions
                if item.status is not MissionStatus.ARCHIVED
            ]

        # The id breaks ties so the order is stable across runs. Without it,
        # two missions created within the same clock tick fall back to the
        # filesystem's UUID ordering, which is effectively random.
        return sorted(
            missions,
            key=lambda item: (-int(item.priority), item.created_at, str(item.id)),
        )

    def delete(self, mission_id: UUID) -> None:
        path = self._path(mission_id)

        if not path.exists():
            raise MissionNotFoundError(f"No mission '{mission_id}' in the backlog.")

        path.unlink()

    def exists(self, mission_id: UUID) -> bool:
        return self._path(mission_id).exists()

    def _ids(self) -> list[UUID]:
        if not self._root.exists():
            return []

        ids = []

        for path in sorted(self._root.glob("*.json")):
            try:
                ids.append(UUID(path.stem))
            except ValueError:
                continue

        return ids

    def _path(self, mission_id: UUID) -> Path:
        return self._root / f"{mission_id}.json"
