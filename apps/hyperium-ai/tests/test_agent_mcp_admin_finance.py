"""End-to-end: the agent tool-use loop drives the admin-finance MCP connector.

This exercises the whole seam that unit tests otherwise leave uncovered:
AgentRunner -> McpTool -> McpClient -> (stdio JSON-RPC) -> the real
admin-finance MCP server (apps/admin-finance/mcp/server.mjs) -> (HTTP) -> a
stubbed finance API. It proves:
  * the read-only tool (finance_get_settings) runs WITHOUT approval,
  * the write tool (finance_prepare_invoice) is held at the approval gate,
  * both tool results flow back into the conversation.

Gating is not configured here — it is derived from each tool's readOnlyHint as
declared by the server, which is exactly what we want to verify.

Skips cleanly when Node or the sibling admin-finance app is unavailable, so it
never fails CI on an environment without them.
"""

from __future__ import annotations

import json
import shutil
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.agents.approval import ActionRequest, ApprovalDecision
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.interfaces.approver import Approver
from infrastructure.mcp.mcp_client import McpClient
from infrastructure.mcp.mcp_toolset import connect_mcp_tools

# tests -> hyperium-ai -> apps -> admin-finance/mcp/server.mjs
SERVER = Path(__file__).resolve().parents[2] / "admin-finance" / "mcp" / "server.mjs"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or not SERVER.exists(),
    reason="needs Node and the sibling admin-finance MCP server (server.mjs)",
)


class ScriptedProvider(AgentProvider):
    """Returns a pre-set sequence of turns (mirrors tests/test_agent_runner.py)."""

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = []

    def chat(self, messages, tools):
        self.calls.append([dict(m) for m in messages])
        return self._turns.pop(0)


class SpyApprover(Approver):
    """Records every action that reaches the approval gate, then allows it."""

    def __init__(self):
        self.reviewed: list[ActionRequest] = []

    def review(self, request: ActionRequest) -> ApprovalDecision:
        self.reviewed.append(request)
        return ApprovalDecision.allow("approved by spy")


class _StubFinanceAPI(BaseHTTPRequestHandler):
    """The smallest finance API the two tools need to reach over HTTP."""

    def log_message(self, *_):  # keep the test output quiet
        pass

    def _send(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/settings":
            return self._send(
                {
                    "company": {"name": "Hyperium BV", "vatNumber": "BE0123.456.789"},
                    "financial": {"standardVatRatePct": 21},
                }
            )
        self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        self.rfile.read(length)  # drain the body; the stub doesn't need it
        if self.path == "/api/invoices":
            return self._send({"id": "inv-1", "number": "2099-001", "status": "draft"})
        self.send_error(404)


@contextmanager
def _stub_api():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _StubFinanceAPI)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()


def test_agent_drives_admin_finance_mcp_tools_end_to_end():
    provider = ScriptedProvider(
        [
            AgentTurn(tool_calls=[ToolCall(name="finance_get_settings", arguments={})]),
            AgentTurn(
                tool_calls=[
                    ToolCall(
                        name="finance_prepare_invoice",
                        arguments={"customerId": "c1", "date": "2099-01-01"},
                    )
                ]
            ),
            AgentTurn(content="Prepared the draft invoice."),
        ]
    )
    spy = SpyApprover()

    with _stub_api() as base_url:
        with McpClient("node", [str(SERVER)], env={"ADMIN_FINANCE_API": base_url}) as client:
            tools = connect_mcp_tools(client)
            names = {t.name for t in tools}
            assert {"finance_get_settings", "finance_prepare_invoice"} <= names

            # Gating is declared by the server (readOnlyHint), not by the test.
            gated = {t.name for t in tools if t.requires_approval}
            assert "finance_get_settings" not in gated
            assert "finance_prepare_invoice" in gated

            runner = AgentRunner(provider, tools, approver=spy)
            result = runner.run("get settings, then prepare an invoice")

    # Only the write tool reached the approval gate.
    assert [r.tool for r in spy.reviewed] == ["finance_prepare_invoice"]
    # Both tool results flowed back through the loop, in order.
    assert [s.tool for s in result.steps] == ["finance_get_settings", "finance_prepare_invoice"]
    assert "Hyperium BV" in result.steps[0].result
    assert "2099-001" in result.steps[1].result
    assert result.output == "Prepared the draft invoice."
