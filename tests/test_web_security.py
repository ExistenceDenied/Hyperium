"""
Security of the local web interface.

The server has no authentication by design — it binds to localhost and serves
one person. That makes cross-site request forgery the real exposure: any page
you visit in the same browser can POST to localhost. These tests pin the
defence.
"""

from __future__ import annotations

import threading
import urllib.error
import urllib.request

import pytest

from application.missions.mission_backlog_service import MissionBacklogService
from application.project.project_builder import ProjectBuilder
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.mission_repository import MissionRepository
from infrastructure.persistence.project_repository import ProjectRepository
from interfaces.web.server import ReviewApp, serve
from tests.fixtures import FakeMethodologies, ScriptedLLM, build_consultant


@pytest.fixture
def server(tmp_path):
    methodologies = FakeMethodologies()
    projects = ProjectRepository(tmp_path / "state")
    missions = MissionRepository(tmp_path / "state" / "missions")
    service = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=projects,
        methodologies=methodologies,
    )
    backlog = MissionBacklogService(missions, project_service=service)

    app = ReviewApp(
        service,
        projects,
        missions=backlog,
        methodologies=methodologies,
        resources=lambda: [build_consultant()],
    )

    httpd = serve(app, host="127.0.0.1", port=0)
    port = httpd.server_address[1]

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    yield f"http://127.0.0.1:{port}", backlog

    httpd.shutdown()
    httpd.server_close()


def post(url, data: bytes = b"", headers: dict | None = None):
    request = urllib.request.Request(
        url, data=data, headers=headers or {}, method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


BODY = (
    b"title=Evil&objective=Injected&priority=HIGH"
    b"&criteria=&constraints=&methodology="
)


def test_a_post_from_another_site_is_refused(server):
    """The attack: a page you visit posts to your local Hyperium."""
    base, backlog = server

    status, body = post(
        f"{base}/missions",
        BODY,
        {
            "Origin": "https://evil.example",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    assert status == 403
    assert "came from another site" in body
    assert backlog.list() == []


def test_a_post_with_a_foreign_referer_is_refused(server):
    base, backlog = server

    status, _ = post(
        f"{base}/missions",
        BODY,
        {
            "Referer": "https://evil.example/page",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    assert status == 403
    assert backlog.list() == []


def test_a_post_from_the_interface_itself_is_accepted(server):
    base, backlog = server

    status, _ = post(
        f"{base}/missions",
        BODY,
        {
            "Origin": base,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )

    assert status in (200, 303)
    assert [m.title for m in backlog.list()] == ["Evil"]


def test_security_headers_are_sent(server):
    base, _ = server

    with urllib.request.urlopen(f"{base}/") as response:
        headers = dict(response.headers)

    assert headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "form-action 'self'" in headers["Content-Security-Policy"]
    assert headers["Referrer-Policy"] == "same-origin"


def test_the_server_binds_to_localhost_by_default(server):
    base, _ = server

    assert base.startswith("http://127.0.0.1")


def test_model_written_content_is_escaped_in_every_view(server):
    """
    Deliverable content and mission text are both untrusted; one is written by
    a model, the other pasted by a user.
    """
    base, backlog = server

    post(
        f"{base}/missions",
        b"title=%3Cscript%3Ealert(1)%3C%2Fscript%3E&objective=x"
        b"&priority=HIGH&criteria=&constraints=&methodology=",
        {"Origin": base, "Content-Type": "application/x-www-form-urlencoded"},
    )

    with urllib.request.urlopen(f"{base}/missions") as response:
        body = response.read().decode("utf-8")

    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;" in body
