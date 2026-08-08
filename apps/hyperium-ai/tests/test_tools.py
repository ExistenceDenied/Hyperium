from __future__ import annotations

from infrastructure.tools.list_directory_tool import ListDirectoryTool
from infrastructure.tools.read_file_tool import ReadFileTool
from infrastructure.tools.web_fetch_tool import WebFetchTool
from infrastructure.tools.write_file_tool import WriteFileTool


def test_read_file_reads_within_root(tmp_path):
    (tmp_path / "note.txt").write_text("hello", encoding="utf-8")
    tool = ReadFileTool(tmp_path)

    assert tool.invoke({"path": "note.txt"}) == "hello"


def test_read_file_refuses_to_escape_root(tmp_path):
    secret = tmp_path / "secret.txt"
    secret.write_text("nope", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    tool = ReadFileTool(root)

    result = tool.invoke({"path": "../secret.txt"})

    assert "outside the permitted directory" in result


def test_read_file_reports_a_missing_file(tmp_path):
    tool = ReadFileTool(tmp_path)

    assert "does not exist" in tool.invoke({"path": "missing.txt"})


def test_list_directory_lists_entries(tmp_path):
    (tmp_path / "a.txt").write_text("", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    tool = ListDirectoryTool(tmp_path)

    listing = tool.invoke({"path": "."})

    assert "a.txt" in listing
    assert "sub/" in listing


def test_web_fetch_rejects_non_http_urls():
    tool = WebFetchTool()

    assert "only http and https" in tool.invoke({"url": "file:///etc/passwd"})


def test_write_file_creates_a_file_within_root(tmp_path):
    tool = WriteFileTool(tmp_path)

    result = tool.invoke({"path": "out/report.md", "content": "hello"})

    assert (tmp_path / "out" / "report.md").read_text(encoding="utf-8") == "hello"
    assert "Wrote 5 characters" in result


def test_write_file_refuses_to_escape_root(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    tool = WriteFileTool(root)

    result = tool.invoke({"path": "../escape.txt", "content": "x"})

    assert "outside the permitted directory" in result
    assert not (tmp_path / "escape.txt").exists()


def test_write_file_acts_without_approval_but_still_previews(tmp_path):
    tool = WriteFileTool(tmp_path)

    # Writes to the task's own folder run autonomously — no approval prompt.
    assert tool.requires_approval is False
    preview = tool.preview({"path": "notes.txt", "content": "abcd"})
    assert "Create" in preview
    assert "notes.txt" in preview


def test_read_only_tools_do_not_require_approval(tmp_path):
    assert ReadFileTool(tmp_path).requires_approval is False
    assert ListDirectoryTool(tmp_path).requires_approval is False
    assert WebFetchTool().requires_approval is False


def test_a_tool_advertises_a_function_schema(tmp_path):
    schema = ReadFileTool(tmp_path).schema()

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "read_file"
    assert "path" in schema["function"]["parameters"]["properties"]
