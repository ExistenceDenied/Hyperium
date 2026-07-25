from pathlib import Path


class WorkspaceService:

    def write(self, workspace: Path, filename: str, content: str):

        workspace.mkdir(parents=True, exist_ok=True)

        file = workspace / filename

        file.write_text(
            content,
            encoding="utf-8",
        )

        return file

    def read(self, workspace: Path, filename: str):

        return (workspace / filename).read_text(
            encoding="utf-8",
        )

    def exists(self, workspace: Path, filename: str):

        return (workspace / filename).exists()

    def list_files(self, workspace: Path):

        return list(workspace.glob("*"))
