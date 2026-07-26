from __future__ import annotations

import json

from infrastructure.connectors import PRESETS, ConnectionStore
from infrastructure.mcp.verify import VerifyResult
from interfaces.web.server import ReviewApp


def _ok_verifier(spec):
    return VerifyResult(True, 3, "Connected — 3 tools available.")


def _fail_verifier(spec):
    return VerifyResult(False, 0, "Could not start the connector: not signed in.")


def test_enabling_a_connector_writes_a_usable_mcp_spec(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")

    store.enable("gmail")

    assert "gmail" in store.enabled_keys()
    specs = store.specs()
    assert "gmail" in specs
    assert specs["gmail"].command == PRESETS["gmail"].command


def test_disabling_removes_it(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    store.enable("files")
    store.disable("files")

    assert store.enabled_keys() == set()


def test_enable_rejects_an_unknown_connector(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")

    try:
        store.enable("not-a-real-connector")
        raised = False
    except KeyError:
        raised = True

    assert raised


def test_connections_page_lists_presets_and_status(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    store.enable("gmail")
    app = ReviewApp(service=None, projects=None, connections=store)

    code, body = app.get("/connections", {})

    assert code == 200
    assert "Gmail" in body
    assert "Xero" in body
    assert "Jira" in body
    assert "Connected" in body  # gmail shows as connected


def test_enable_writes_a_path_argument_and_env_credentials(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")

    store.enable("files", {"path": r"C:\work"})
    store.enable("jira", {"site": "acme", "email": "a@b.com", "token": "secret"})

    assert store.specs()["files"].args[-1] == r"C:\work"
    jira_env = store.specs()["jira"].env
    assert jira_env["ATLASSIAN_SITE_NAME"] == "acme"
    assert jira_env["ATLASSIAN_API_TOKEN"] == "secret"


def test_connect_collects_input_then_verifies(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    app = ReviewApp(
        service=None,
        projects=None,
        connections=store,
        verify_connector=_ok_verifier,
    )

    code, body = app.post("/connections/files/connect", {"path": [r"C:\work"]})

    assert code == 200
    payload = json.loads(body)
    assert payload["ok"] is True and payload["tools"] == 3
    assert store.specs()["files"].args[-1] == r"C:\work"  # input was saved

    app.post("/connections/files/disconnect", {})
    assert "files" not in store.enabled_keys()


def test_connect_reports_failure_but_keeps_it_registered_to_retry(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    app = ReviewApp(
        service=None,
        projects=None,
        connections=store,
        verify_connector=_fail_verifier,
    )

    code, body = app.post("/connections/outlook/connect", {})

    payload = json.loads(body)
    assert code == 200 and payload["ok"] is False
    assert "not signed in" in payload["message"]
    assert "outlook" in store.enabled_keys()  # retained so Verify can be retried


def test_verify_route_reports_a_registered_connector(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    store.enable("files", {"path": r"C:\work"})
    app = ReviewApp(
        service=None,
        projects=None,
        connections=store,
        verify_connector=_ok_verifier,
    )

    code, body = app.post("/connections/files/verify", {})

    assert code == 200 and json.loads(body)["ok"] is True


def test_the_connect_page_carries_the_wizard_and_field_specs(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    app = ReviewApp(service=None, projects=None, connections=store)

    _, body = app.get("/connections", {})

    assert "data-connect='outlook'" in body  # buttons are wired for the modal
    assert "id='connectors-data'" in body  # data passed as a JSON block
    assert "src='/app.js'" in body  # behaviour loaded from the served script
    assert "XERO_CLIENT_ID" not in body  # secrets' env names are not leaked
    assert '"auth": "device"' in body


def test_app_js_is_served_inline_with_a_script_type(tmp_path):
    app = ReviewApp(service=None, projects=None)

    code, body = app.get("/app.js", {})

    assert code == 200
    assert body.media_type.startswith("application/javascript")
    assert body.inline is True
    assert "openWizard" in body.content and "alert-badge" in body.content
