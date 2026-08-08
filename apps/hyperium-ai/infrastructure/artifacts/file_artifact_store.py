from __future__ import annotations

from pathlib import Path

from core.interfaces.artifact_store import ArtifactStore


class FileArtifactStore(ArtifactStore):
    """
    Stores deliverable content as files under a workspace directory.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    def save(self, filename: str, content: str) -> str:
        self._root.mkdir(parents=True, exist_ok=True)

        path = self._root / filename
        path.write_text(content, encoding="utf-8")

        return str(path)

    def read(self, filename: str) -> str:
        return (self._root / filename).read_text(encoding="utf-8")


class InMemoryArtifactStore(ArtifactStore):
    """
    Non-persistent store, used by tests and dry runs.
    """

    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    def save(self, filename: str, content: str) -> str:
        self.files[filename] = content
        return f"memory://{filename}"

    def read(self, filename: str) -> str:
        return self.files[filename]
