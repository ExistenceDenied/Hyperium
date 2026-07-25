from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.scoped import confine

MAX_ENTRIES = 200


class ListDirectoryTool(Tool):
    """List the entries of a directory, confined to a root directory."""

    name = "list_directory"
    description = (
        "List the files and subdirectories of a directory. Use this to "
        "discover what files exist. Paths are relative to the working root."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory path relative to the root; '.' is the root.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def invoke(self, arguments: dict) -> str:
        raw = str(arguments.get("path", ".")).strip() or "."
        target = confine(self._root, raw)

        if target is None:
            return f"Error: '{raw}' is outside the permitted directory."

        if not target.is_dir():
            return f"Error: '{raw}' is not a directory."

        entries = sorted(
            f"{child.name}/" if child.is_dir() else child.name
            for child in target.iterdir()
        )[:MAX_ENTRIES]

        return "\n".join(entries) if entries else "(empty directory)"
