from __future__ import annotations

from infrastructure.mcp import launch
from infrastructure.mcp.launch import resolve_argv
from infrastructure.mcp.mcp_client import McpClient


def test_windows_resolves_npx_cmd_through_cmd(monkeypatch):
    monkeypatch.setattr(launch.os, "name", "nt")
    monkeypatch.setattr(launch.shutil, "which", lambda cmd: r"C:\nodejs\npx.cmd")

    # A .cmd cannot be launched by CreateProcess directly — it must go via cmd.
    assert resolve_argv("npx", ["-y", "@some/server"]) == [
        "cmd",
        "/c",
        r"C:\nodejs\npx.cmd",
        "-y",
        "@some/server",
    ]


def test_posix_uses_the_resolved_path_directly(monkeypatch):
    monkeypatch.setattr(launch.os, "name", "posix")
    monkeypatch.setattr(launch.shutil, "which", lambda cmd: "/usr/bin/npx")

    assert resolve_argv("npx", ["-y", "@some/server"]) == [
        "/usr/bin/npx",
        "-y",
        "@some/server",
    ]


def test_falls_back_to_the_bare_command_when_not_on_path(monkeypatch):
    monkeypatch.setattr(launch.os, "name", "posix")
    monkeypatch.setattr(launch.shutil, "which", lambda cmd: None)

    assert resolve_argv("mytool", ["--stdio"]) == ["mytool", "--stdio"]


def test_mcp_client_uses_the_shared_resolver(monkeypatch):
    monkeypatch.setattr(launch.os, "name", "nt")
    monkeypatch.setattr(launch.shutil, "which", lambda cmd: r"C:\nodejs\npx.cmd")

    client = McpClient("npx", ["-y", "@some/server"])

    assert client._argv()[:3] == ["cmd", "/c", r"C:\nodejs\npx.cmd"]
