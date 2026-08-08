#!/usr/bin/env python3
"""
A minimal MCP server over stdio — a worked example and a test fixture.

It exposes two tools so the difference the agent cares about is visible:

- ``list_notes`` is annotated ``readOnlyHint: true`` — the agent may call it
  without asking.
- ``add_note`` changes state, so it is *not* read-only and the runner holds it
  at the approval gate.

Point Hyperium at a real MCP server the same way — email, calendar, files —
and its tools appear to the agent with the same read/act distinction. Run:

    hyperium do "..." --mcp examples/mcp/notes.mcp.json
"""

from __future__ import annotations

import json
import sys

NOTES: list[str] = []

TOOLS = [
    {
        "name": "list_notes",
        "description": "List every note that has been saved.",
        "inputSchema": {"type": "object", "properties": {}},
        "annotations": {"title": "List notes", "readOnlyHint": True},
    },
    {
        "name": "add_note",
        "description": "Save a note for later.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The note to save."}
            },
            "required": ["text"],
        },
        "annotations": {"title": "Add note", "readOnlyHint": False},
    },
]


def send(message: dict) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()


def call_tool(name: str, arguments: dict) -> str:
    if name == "add_note":
        NOTES.append(str(arguments.get("text", "")))
        return f"Saved. {len(NOTES)} note(s) stored."

    if name == "list_notes":
        return "\n".join(f"- {note}" for note in NOTES) or "(no notes yet)"

    raise KeyError(name)


def main() -> None:
    sys.stdin.reconfigure(encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        message = json.loads(line)
        request_id = message.get("id")
        method = message.get("method")

        if method == "initialize":
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "notes", "version": "0.1"},
                    },
                }
            )
        elif method == "notifications/initialized":
            continue  # a notification: acknowledged by doing nothing
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = message.get("params", {})
            try:
                text = call_tool(params.get("name"), params.get("arguments", {}))
            except KeyError as unknown:
                send(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": f"unknown tool {unknown}",
                        },
                    }
                )
                continue

            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": text}]},
                }
            )
        elif request_id is not None:
            send(
                {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"unknown method {method}"},
                }
            )


if __name__ == "__main__":
    main()
