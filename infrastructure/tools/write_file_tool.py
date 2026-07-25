from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.scoped import confine


class WriteFileTool(Tool):
    """Create or overwrite a UTF-8 text file, confined to a root directory."""

    name = "write_file"
    description = (
        "Write text to a file, creating it or overwriting it. Paths are "
        "relative to the working root. This changes the filesystem, so it "
        "requires approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the working root.",
            },
            "content": {
                "type": "string",
                "description": "The full text to write.",
            },
        },
        "required": ["path", "content"],
    }
    requires_approval = True

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def preview(self, arguments: dict) -> str:
        raw = str(arguments.get("path", "")).strip()
        content = str(arguments.get("content", ""))
        target = confine(self._root, raw) if raw else None

        if target is None:
            return f"Refuse to write '{raw}': outside the permitted directory."

        verb = "Overwrite" if target.exists() else "Create"

        return f"{verb} {raw} ({len(content)} chars) under {self._root}."

    def invoke(self, arguments: dict) -> str:
        raw = str(arguments.get("path", "")).strip()
        content = str(arguments.get("content", ""))

        if not raw:
            return "Error: no path was provided."

        target = confine(self._root, raw)

        if target is None:
            return f"Error: '{raw}' is outside the permitted directory."

        if target.is_dir():
            return f"Error: '{raw}' is a directory."

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

        return f"Wrote {len(content)} characters to {raw}."
