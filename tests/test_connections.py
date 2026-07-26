from __future__ import annotations

from infrastructure.connectors import PRESETS, ConnectionStore
from interfaces.web.server import ReviewApp


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


def test_connect_and_disconnect_routes(tmp_path):
    store = ConnectionStore(tmp_path / "connections.json")
    app = ReviewApp(service=None, projects=None, connections=store)

    code, redirect = app.post("/connections/files/connect", {})
    assert code == 303 and redirect == "/connections"
    assert "files" in store.enabled_keys()

    app.post("/connections/files/disconnect", {})
    assert "files" not in store.enabled_keys()
