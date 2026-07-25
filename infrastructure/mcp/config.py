from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class McpServerSpec:
    """How to launch one MCP server."""

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None


def load_mcp_config(path: Path) -> dict[str, McpServerSpec]:
    """
    Read a JSON file describing the MCP servers to connect.

    The shape mirrors the widely used ``mcpServers`` convention, so a config
    that already drives another MCP host can be reused::

        {
          "servers": {
            "notes": {"command": "python", "args": ["notes_server.py"]}
          }
        }
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    servers = data.get("servers") or data.get("mcpServers") or {}

    result: dict[str, McpServerSpec] = {}

    for name, spec in servers.items():
        result[name] = McpServerSpec(
            command=spec["command"],
            args=list(spec.get("args") or []),
            env=spec.get("env"),
        )

    return result
