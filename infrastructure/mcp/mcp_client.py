from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time
from collections.abc import Mapping, Sequence

PROTOCOL_VERSION = "2024-11-05"


class McpError(RuntimeError):
    """A failure talking to an MCP server."""


class McpClient:
    """
    A minimal, synchronous MCP client over stdio.

    It launches an MCP server as a subprocess and speaks newline-delimited
    JSON-RPC 2.0 to it: initialize, list tools, call a tool. This is the seam
    that lets Hyperium reach whatever a business already exposes over MCP —
    email, calendar, files, a knowledge base — without a bespoke adapter per
    service, and without leaving the local machine.

    Deliberately dependency-free: the whole transport is stdlib subprocess plus
    a background reader thread, so it fits the platform's minimal-dependency
    rule and runs the same on Windows as on Linux.

    Not yet handled: paginated ``tools/list`` cursors, and server-initiated
    requests (sampling, roots). Both are unused by the read/act tools this
    connects today.
    """

    def __init__(
        self,
        command: str,
        args: Sequence[str] = (),
        env: Mapping[str, str] | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._command = command
        self._args = list(args)
        self._env = {**os.environ, **env} if env else None
        self._timeout = timeout_seconds
        self._proc: subprocess.Popen | None = None
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._id = 0

    def __enter__(self) -> "McpClient":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()

    def start(self) -> "McpClient":
        self._proc = subprocess.Popen(
            [self._command, *self._args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=self._env,
        )

        reader = threading.Thread(target=self._read_loop, daemon=True)
        reader.start()

        self._initialize()

        return self

    def list_tools(self) -> list[dict]:
        return self._request("tools/list", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        result = self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )

        blocks = result.get("content") or []
        text = "\n".join(
            block.get("text", "")
            for block in blocks
            if block.get("type") == "text"
        )

        if result.get("isError"):
            return f"Error from tool '{name}': {text}".strip()

        return text or "(the tool returned no textual content)"

    def close(self) -> None:
        if self._proc is None:
            return

        try:
            if self._proc.stdin is not None:
                self._proc.stdin.close()
        except OSError:
            pass

        self._proc.terminate()

        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()

        self._proc = None

    # ------------------------------------------------------------- internals

    def _initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "Hyperium", "version": "0.2"},
            },
        )
        # A notification, not a request: no id, and no response is expected.
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _read_loop(self) -> None:
        stdout = self._proc.stdout if self._proc else None

        if stdout is None:
            return

        for line in stdout:
            line = line.strip()
            if line:
                self._queue.put(line)

        # Sentinel: the server closed its output, so no reply is ever coming.
        self._queue.put(None)

    def _send(self, message: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("the MCP server is not running")

        self._proc.stdin.write(json.dumps(message) + "\n")
        self._proc.stdin.flush()

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._id += 1
        request_id = self._id

        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )

        deadline = time.monotonic() + self._timeout

        while True:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                raise McpError(f"timed out waiting for a reply to '{method}'")

            try:
                item = self._queue.get(timeout=remaining)
            except queue.Empty:
                raise McpError(f"timed out waiting for a reply to '{method}'")

            if item is None:
                raise McpError("the MCP server closed the connection")

            message = json.loads(item)

            # Skip notifications and replies to other requests.
            if message.get("id") != request_id:
                continue

            if "error" in message:
                raise McpError(str(message["error"]))

            return message.get("result", {})
