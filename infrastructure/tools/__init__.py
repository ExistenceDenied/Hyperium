from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.excel_tools import (
    ReadExcelTool,
    UpdateExcelCellTool,
    WriteExcelTool,
)
from infrastructure.tools.list_directory_tool import ListDirectoryTool
from infrastructure.tools.office_tools import WritePowerPointTool, WriteWordTool
from infrastructure.tools.read_file_tool import ReadFileTool
from infrastructure.tools.web_fetch_tool import WebFetchTool
from infrastructure.tools.write_file_tool import WriteFileTool

__all__ = [
    "ListDirectoryTool",
    "ReadExcelTool",
    "ReadFileTool",
    "UpdateExcelCellTool",
    "WebFetchTool",
    "WriteExcelTool",
    "WriteFileTool",
    "WritePowerPointTool",
    "WriteWordTool",
    "read_only_tools",
    "writable_tools",
]


def read_only_tools(root: Path, *, timeout_seconds: float = 30.0) -> list[Tool]:
    """
    The tools an agent may use without approval.

    Every tool here is read-only: it observes the world — a file, a directory,
    a URL, a spreadsheet — and cannot change it.
    """
    return [
        ReadFileTool(root),
        ListDirectoryTool(root),
        WebFetchTool(timeout_seconds=timeout_seconds),
        ReadExcelTool(root),
    ]


def writable_tools(root: Path, *, timeout_seconds: float = 30.0) -> list[Tool]:
    """
    The read-only tools plus those that write files.

    These write only inside ``root`` — the task's own folder — so they act
    without approval: the point is that the agent produces its deliverables
    autonomously, and the folder confinement is the boundary, not a prompt. A
    file, a spreadsheet, a Word document or a PowerPoint deck all land in the
    task's directory. (Connector tools, which act on the outside world, keep
    their approval gate.)
    """
    return [
        *read_only_tools(root, timeout_seconds=timeout_seconds),
        WriteFileTool(root),
        WriteExcelTool(root),
        UpdateExcelCellTool(root),
        WriteWordTool(root),
        WritePowerPointTool(root),
    ]
