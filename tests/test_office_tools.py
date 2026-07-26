from __future__ import annotations

import pytest

# The tools produce real Office files, which need the optional office extra.
pytest.importorskip("pptx")
pytest.importorskip("docx")

from infrastructure.tools import writable_tools  # noqa: E402
from infrastructure.tools.office_tools import (  # noqa: E402
    WritePowerPointTool,
    WriteWordTool,
)

_OUTLINE = """# Value case

## Problem
Teams waste time on email.

## Proposal
- Triage automatically
- Draft replies
Note: emphasise the time saved.
"""


def test_powerpoint_tool_writes_a_real_pptx(tmp_path):
    result = WritePowerPointTool(tmp_path).invoke(
        {"path": "deck", "title": "Hyperium", "content": _OUTLINE}
    )

    out = tmp_path / "deck.pptx"  # extension added automatically
    assert out.is_file() and out.stat().st_size > 0
    assert "Wrote PowerPoint deck" in result

    from pptx import Presentation

    deck = Presentation(str(out))
    assert len(deck.slides) >= 3  # title + Problem + Proposal


def test_word_tool_writes_a_real_docx(tmp_path):
    result = WriteWordTool(tmp_path).invoke(
        {"path": "report.docx", "title": "Report", "content": "# Intro\n\nHello."}
    )

    out = tmp_path / "report.docx"
    assert out.is_file() and out.stat().st_size > 0
    assert "Wrote Word document" in result


def test_tools_are_confined_to_the_root(tmp_path):
    result = WriteWordTool(tmp_path).invoke(
        {"path": "../escape.docx", "title": "x", "content": "y"}
    )
    assert "outside the permitted directory" in result
    assert not (tmp_path.parent / "escape.docx").exists()


def test_office_tools_are_offered_to_a_writing_agent(tmp_path):
    names = {t.name for t in writable_tools(tmp_path)}
    assert {"write_powerpoint", "write_word"} <= names
