from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.list_directory_tool import ListDirectoryTool
from infrastructure.tools.read_file_tool import ReadFileTool
from infrastructure.tools.web_fetch_tool import WebFetchTool

__all__ = [
    "ListDirectoryTool",
    "ReadFileTool",
    "WebFetchTool",
    "read_only_tools",
]


def read_only_tools(root: Path, *, timeout_seconds: float = 30.0) -> list[Tool]:
    """
    The tools an agent may use without approval.

    Every tool here is read-only: it observes the world — a file, a directory,
    a URL — and cannot change it. Side-effecting tools (sending, writing,
    deleting) are deliberately absent until the approval gate lands in Slice 2.
    """
    return [
        ReadFileTool(root),
        ListDirectoryTool(root),
        WebFetchTool(timeout_seconds=timeout_seconds),
    ]
