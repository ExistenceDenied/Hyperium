from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.documents import to_docx, to_pptx
from infrastructure.tools.scoped import confine


class WritePowerPointTool(Tool):
    """Produce a .pptx deck from a slide outline, confined to a root directory."""

    name = "write_powerpoint"
    description = (
        "Create a PowerPoint (.pptx) deck and save it. Give the deck content as "
        "Markdown: each '## Heading' starts a new slide and the lines under it "
        "become that slide's bullets; a line beginning 'Note:' becomes a speaker "
        "note. Use this to actually deliver a presentation — do not say you "
        "cannot make one."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File to write, e.g. deck.pptx."},
            "title": {"type": "string", "description": "Title-slide heading."},
            "content": {
                "type": "string",
                "description": "The slide outline as Markdown (## per slide).",
            },
        },
        "required": ["path", "title", "content"],
    }
    requires_approval = True

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def preview(self, arguments: dict) -> str:
        return f"Create a PowerPoint deck at {arguments.get('path')}."

    def invoke(self, arguments: dict) -> str:
        return _write(self._root, arguments, to_pptx, ".pptx", "PowerPoint deck")


class WriteWordTool(Tool):
    """Produce a .docx document from Markdown, confined to a root directory."""

    name = "write_word"
    description = (
        "Create a Word (.docx) document and save it. Give the content as "
        "Markdown — headings, paragraphs, bullet and numbered lists and tables "
        "all come through as real Word formatting. Use this to deliver a "
        "report, proposal or letter as a Word file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File to write, e.g. report.docx.",
            },
            "title": {"type": "string", "description": "Document title."},
            "content": {
                "type": "string",
                "description": "The document body as Markdown.",
            },
        },
        "required": ["path", "title", "content"],
    }
    requires_approval = True

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def preview(self, arguments: dict) -> str:
        return f"Create a Word document at {arguments.get('path')}."

    def invoke(self, arguments: dict) -> str:
        return _write(self._root, arguments, to_docx, ".docx", "Word document")


def _write(root: Path, arguments: dict, render, suffix: str, label: str) -> str:
    raw = str(arguments.get("path", "")).strip()
    if raw and not raw.lower().endswith(suffix):
        raw += suffix
    target = confine(root, raw) if raw else None

    if target is None:
        return f"Error: '{raw}' is outside the permitted directory."

    title = str(arguments.get("title", "")).strip() or "Untitled"
    content = str(arguments.get("content", ""))

    try:
        data = render(title, content)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    except Exception as error:
        return f"Error: could not write '{raw}': {error}"

    return f"Wrote {label} to {raw} ({len(data)} bytes)."
