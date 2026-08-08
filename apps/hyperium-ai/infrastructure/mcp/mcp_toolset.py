from __future__ import annotations

from core.tools.tool import Tool
from infrastructure.mcp.mcp_client import McpClient


class McpTool(Tool):
    """
    A tool exposed by an MCP server, presented to the agent like any other.

    Whether it needs approval is not guessed: it comes from the server's own
    ``readOnlyHint`` annotation. A tool the server declares read-only runs
    freely; everything else — anything that might send, change or delete — is
    held at the approval gate, which is the safe default for an external tool.
    """

    def __init__(
        self,
        client: McpClient,
        name: str,
        description: str | None,
        parameters: dict | None,
        requires_approval: bool,
    ) -> None:
        self._client = client
        self.name = name
        self.description = description or f"External tool '{name}' (via MCP)."
        self.parameters = parameters or {"type": "object", "properties": {}}
        self.requires_approval = requires_approval

    def preview(self, arguments: dict) -> str:
        return f"call the external tool '{self.name}' with {arguments}"

    def invoke(self, arguments: dict) -> str:
        return self._client.call_tool(self.name, arguments)


def connect_mcp_tools(client: McpClient) -> list[Tool]:
    """Turn every tool an MCP server advertises into a Hyperium tool."""
    tools: list[Tool] = []

    for spec in client.list_tools():
        annotations = spec.get("annotations") or {}
        read_only = bool(annotations.get("readOnlyHint", False))

        tools.append(
            McpTool(
                client,
                spec["name"],
                spec.get("description"),
                spec.get("inputSchema"),
                requires_approval=not read_only,
            )
        )

    return tools
