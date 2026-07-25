from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.scoped import confine

MAX_BYTES = 100_000


class ReadFileTool(Tool):
    """Read a UTF-8 text file, confined to a root directory."""

    name = "read_file"
    description = (
        "Read the contents of a UTF-8 text file. Use this before answering any "
        "question about a file. Paths are relative to the working root."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the working root.",
            }
        },
        "required": ["path"],
    }

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def invoke(self, arguments: dict) -> str:
        raw = str(arguments.get("path", "")).strip()

        if not raw:
            return "Error: no path was provided."

        target = confine(self._root, raw)

        if target is None:
            return f"Error: '{raw}' is outside the permitted directory."

        if not target.is_file():
            return f"Error: '{raw}' is not a file."

        data = target.read_bytes()[:MAX_BYTES]

        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return f"Error: '{raw}' is not valid UTF-8 text."
