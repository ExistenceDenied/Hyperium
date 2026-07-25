from __future__ import annotations

import sys
from pathlib import Path

from infrastructure.mcp.config import load_mcp_config
from infrastructure.mcp.mcp_client import McpClient
from infrastructure.mcp.mcp_toolset import connect_mcp_tools

SERVER = (
    Path(__file__).resolve().parent.parent / "examples" / "mcp" / "notes_server.py"
)


def _client() -> McpClient:
    # sys.executable, not "python": the test must run the interpreter it was
    # launched with, whatever the platform names it.
    return McpClient(sys.executable, [str(SERVER)])


def test_lists_the_tools_the_server_advertises():
    with _client() as client:
        names = {tool["name"] for tool in client.list_tools()}

    assert names == {"list_notes", "add_note"}


def test_calling_a_tool_round_trips_through_the_server():
    with _client() as client:
        client.call_tool("add_note", {"text": "buy milk"})
        listing = client.call_tool("list_notes", {})

    assert "buy milk" in listing


def test_read_only_hint_decides_whether_approval_is_required():
    with _client() as client:
        tools = {tool.name: tool for tool in connect_mcp_tools(client)}

        # The server annotates list_notes read-only; add_note is not.
        assert tools["list_notes"].requires_approval is False
        assert tools["add_note"].requires_approval is True


def test_mcp_tool_invoke_executes_the_remote_call():
    with _client() as client:
        tools = {tool.name: tool for tool in connect_mcp_tools(client)}

        tools["add_note"].invoke({"text": "hello"})

        assert "hello" in tools["list_notes"].invoke({})


def test_config_loads_server_specs(tmp_path):
    config = tmp_path / "mcp.json"
    config.write_text(
        '{"servers": {"notes": {"command": "python", "args": ["s.py"]}}}',
        encoding="utf-8",
    )

    specs = load_mcp_config(config)

    assert specs["notes"].command == "python"
    assert specs["notes"].args == ["s.py"]
