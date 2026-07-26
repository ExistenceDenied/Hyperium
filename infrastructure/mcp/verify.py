from __future__ import annotations

import threading
from dataclasses import dataclass

from infrastructure.mcp.config import McpServerSpec
from infrastructure.mcp.mcp_client import McpClient


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    tools: int
    message: str


def verify_connector(spec: McpServerSpec, timeout: float = 90.0) -> VerifyResult:
    """
    Actually start the connector and list its tools, to prove it works.

    Establishing the connection *is* the verification: if the server launches,
    initialises and answers with its tools, it is genuinely usable. A first run
    may download the server over npx, so the wait is generous and a timeout is
    reported as "still starting" rather than a failure — trying again succeeds
    once the download is cached.
    """
    outcome: dict = {}

    def run() -> None:
        try:
            with McpClient(
                spec.command, spec.args, env=spec.env, timeout_seconds=timeout
            ) as client:
                tools = client.list_tools()
            outcome["tools"] = len(tools)
        except Exception as error:  # noqa: BLE001 - reported back to the user
            outcome["error"] = str(error) or error.__class__.__name__

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)

    if worker.is_alive():
        return VerifyResult(
            False,
            0,
            "Still starting — a first-time download can be slow. Give it a "
            "moment and press Verify again.",
        )
    if "tools" in outcome:
        count = outcome["tools"]
        return VerifyResult(True, count, f"Connected — {count} tools available.")
    return VerifyResult(
        False,
        0,
        "Could not start the connector: " + outcome.get("error", "unknown error"),
    )
