from __future__ import annotations

import pytest

# Excel output is an optional extra; CI installs only `dev`. Skip rather than
# fail when openpyxl is absent, keeping the unit suite runnable without it.
pytest.importorskip("openpyxl")

from infrastructure.tools.excel_tools import (  # noqa: E402
    ReadExcelTool,
    UpdateExcelCellTool,
    WriteExcelTool,
)


def test_agent_can_produce_and_read_back_a_spreadsheet(tmp_path):
    written = WriteExcelTool(tmp_path).invoke(
        {
            "path": "invoice.xlsx",
            "sheet": "Invoice",
            "rows": [["Item", "Qty", "Price"], ["Tap", "2", "40"]],
        }
    )
    assert "Wrote 2 rows" in written
    assert (tmp_path / "invoice.xlsx").is_file()

    read = ReadExcelTool(tmp_path).invoke({"path": "invoice.xlsx", "sheet": "Invoice"})
    assert "Item" in read and "Tap" in read


def test_agent_can_update_a_cell(tmp_path):
    WriteExcelTool(tmp_path).invoke(
        {"path": "t.xlsx", "rows": [["Item", "Price"], ["Tap", "40"]]}
    )

    updated = UpdateExcelCellTool(tmp_path).invoke(
        {"path": "t.xlsx", "cell": "B2", "value": "45"}
    )
    assert "Set B2" in updated

    read = ReadExcelTool(tmp_path).invoke({"path": "t.xlsx"})
    assert "45" in read


def test_writes_require_approval_but_reads_do_not(tmp_path):
    assert WriteExcelTool(tmp_path).requires_approval is True
    assert UpdateExcelCellTool(tmp_path).requires_approval is True
    assert ReadExcelTool(tmp_path).requires_approval is False


def test_update_reports_a_missing_file(tmp_path):
    result = UpdateExcelCellTool(tmp_path).invoke(
        {"path": "nope.xlsx", "cell": "A1", "value": "x"}
    )
    assert "does not exist" in result


def test_excel_tools_are_confined_to_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()

    result = WriteExcelTool(root).invoke(
        {"path": "../escape.xlsx", "rows": [["a"]]}
    )
    assert "outside the permitted directory" in result
    assert not (tmp_path / "escape.xlsx").exists()
