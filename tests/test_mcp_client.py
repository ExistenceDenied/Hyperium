from __future__ import annotations

from infrastructure.mcp import mcp_client
from infrastructure.mcp.mcp_client import McpClient


def test_windows_resolves_npx_cmd_through_cmd(monkeypatch):
    monkeypatch.setattr(mcp_client.os, "name", "nt")
    monkeypatch.setattr(
        mcp_client.shutil, "which", lambda cmd: r"C:\nodejs\npx.cmd"
    )

    client = McpClient("npx", ["-y", "@some/server"])

    # A .cmd cannot be launched by CreateProcess directly — it must go via cmd.
    assert client._argv() == ["cmd", "/c", r"C:\nodejs\npx.cmd", "-y", "@some/server"]


def test_posix_uses_the_resolved_path_directly(monkeypatch):
    monkeypatch.setattr(mcp_client.os, "name", "posix")
    monkeypatch.setattr(mcp_client.shutil, "which", lambda cmd: "/usr/bin/npx")

    client = McpClient("npx", ["-y", "@some/server"])

    assert client._argv() == ["/usr/bin/npx", "-y", "@some/server"]


def test_falls_back_to_the_bare_command_when_not_on_path(monkeypatch):
    monkeypatch.setattr(mcp_client.os, "name", "posix")
    monkeypatch.setattr(mcp_client.shutil, "which", lambda cmd: None)

    client = McpClient("mytool", ["--stdio"])

    assert client._argv() == ["mytool", "--stdio"]
