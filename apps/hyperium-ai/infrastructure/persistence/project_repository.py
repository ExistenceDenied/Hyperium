from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from core.project.project import Project
from infrastructure.persistence.project_serializer import ProjectSerializer


class ProjectRepository:
    """
    Stores engagements as JSON files, one per project.

    This is what makes the approval gate real: a run can stop, the process can
    exit, a human can take a day to review, and the engagement resumes from
    exactly where it paused.
    """

    def __init__(
        self,
        root: Path,
        serializer: ProjectSerializer | None = None,
    ) -> None:
        self._root = Path(root)
        self._serializer = serializer or ProjectSerializer()

    def save(self, project: Project) -> Path:
        self._root.mkdir(parents=True, exist_ok=True)

        path = self._path(project.id)
        payload = self._serializer.to_dict(project)

        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return path

    def load(self, project_id: UUID) -> Project:
        path = self._path(project_id)

        if not path.exists():
            raise FileNotFoundError(f"No saved engagement at {path}.")

        payload = json.loads(path.read_text(encoding="utf-8"))

        return self._serializer.from_dict(payload)

    def list_ids(self) -> list[UUID]:
        if not self._root.exists():
            return []

        ids = []

        for path in sorted(self._root.glob("*.json")):
            try:
                ids.append(UUID(path.stem))
            except ValueError:
                continue

        return ids

    def exists(self, project_id: UUID) -> bool:
        return self._path(project_id).exists()

    def _path(self, project_id: UUID) -> Path:
        return self._root / f"{project_id}.json"
