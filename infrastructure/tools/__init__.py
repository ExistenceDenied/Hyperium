from __future__ import annotations

from pathlib import Path

from core.tools.tool import Tool
from infrastructure.tools.excel_tools import (
    ReadExcelTool,
    UpdateExcelCellTool,
    WriteExcelTool,
)
from infrastructure.tools.list_directory_tool import ListDirectoryTool
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
    The read-only tools plus those that change the filesystem.

    The side-effecting tools here declare ``requires_approval``, so the runner
    routes each invocation through its approver. Handing these to a runner
    without an approver is safe: the default policy denies every side effect.
    Excel produce/update is here too, so an agent can build and revise a
    spreadsheet — an invoice, a quote, a tracker — under approval.
    """
    return [
        *read_only_tools(root, timeout_seconds=timeout_seconds),
        WriteFileTool(root),
        WriteExcelTool(root),
        UpdateExcelCellTool(root),
    ]
