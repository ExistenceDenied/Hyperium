"""
Web review interface.

The security tests matter here: deliverable content is written by a language
model and is therefore untrusted input rendered into a page.
"""

import pytest

from application.project.project_builder import ProjectBuilder
from core.execution.deliverable_status import DeliverableStatus
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.mission_repository import MissionRepository
from infrastructure.persistence.project_repository import ProjectRepository
from interfaces.web import markdown
from interfaces.web.server import ReviewApp
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


class InlineRunner:
    """Runs work synchronously so tests do not race a thread."""

    def __init__(self):
        self.errors = {}

    def busy(self, project_id):
        return False

    def error(self, project_id):
        return self.errors.get(project_id, "")

    def start(self, project_id, work):
        try:
            work()
        except Exception as error:
            self.errors[project_id] = str(error)


def build(tmp_path):
    methodologies = FakeMethodologies()
    projects = ProjectRepository(tmp_path / "state")
    missions = MissionRepository(tmp_path / "state" / "missions")
    service = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=projects,
        methodologies=methodologies,
    )

    project = service.start(build_mission(), resources=[build_consultant()])
    app = ReviewApp(service, projects, missions, runner=InlineRunner())

    return app, project, projects


# ---------------------------------------------------------------- markdown


def test_markdown_renders_the_common_constructs():
    html = markdown.render(
        "# Title\n\n"
        "Some **bold** and *italic* and `code`.\n\n"
        "- one\n- two\n\n"
        "| a | b |\n|---|---|\n| 1 | 2 |\n\n"
        "```python\nprint('hi')\n```\n"
    )

    assert "<h1>Title</h1>" in html
    assert "<strong>bold</strong>" in html
    assert "<em>italic</em>" in html
    assert "<code>code</code>" in html
    assert "<li>one</li>" in html
    assert "<th>a</th>" in html and "<td>1</td>" in html
    assert "<pre><code" in html


def test_markdown_escapes_html_in_model_output():
    html = markdown.render("Hello <script>alert('xss')</script> world")

    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_markdown_escapes_html_inside_code_fences():
    html = markdown.render("```\n<img src=x onerror=alert(1)>\n```")

    assert "<img" not in html
    assert "&lt;img" in html


def test_markdown_refuses_javascript_links():
    html = markdown.render("[click me](javascript:alert(1))")

    assert "href" not in html
    assert "click me" in html


def test_markdown_allows_http_links():
    html = markdown.render("[docs](https://example.com/x)")

    assert 'href="https://example.com/x"' in html


def test_markdown_escapes_a_crafted_link_target():
    html = markdown.render('[x](https://a.com/"onmouseover="alert(1))')

    assert 'onmouseover="alert' not in html


# ------------------------------------------------------------------ pages


def test_index_lists_engagements_and_flags_pending_review(tmp_path):
    app, project, _ = build(tmp_path)

    status, body = app.get("/engagements", {})

    assert status == 200
    assert "Business Analysis training" in body or project.mission.title in body
    assert "waiting for your review" in body


def test_engagement_page_shows_deliverables_and_a_review_form(tmp_path):
    app, project, _ = build(tmp_path)

    status, body = app.get(f"/engagement/{project.id}", {})

    assert status == 200
    assert "AWAITING APPROVAL" in body
    assert "name='decision' value='approve'" in body
    assert "name='decision' value='reject'" in body


def test_deliverable_page_renders_the_content(tmp_path):
    app, project, _ = build(tmp_path)

    status, body = app.get(
        f"/engagement/{project.id}/deliverable/requirements", {}
    )

    assert status == 200
    assert "Juniors must run an intake workshop." in body


def test_unknown_engagement_is_a_404(tmp_path):
    app, _, _ = build(tmp_path)

    status, body = app.get("/engagement/not-a-uuid", {})

    assert status == 404


def test_unknown_deliverable_is_a_404(tmp_path):
    app, project, _ = build(tmp_path)

    status, _ = app.get(f"/engagement/{project.id}/deliverable/nope", {})

    assert status == 404


# ----------------------------------------------------------------- review


def test_approving_through_the_web_persists_the_decision(tmp_path):
    app, project, projects = build(tmp_path)

    status, location = app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["approve"], "note": ["Looks good."]},
    )

    assert status == 303
    assert location == f"/engagement/{project.id}"

    stored = projects.load(project.id)

    assert stored.deliverable("requirements").is_approved
    assert (
        stored.deliverable("requirements").latest_version().review_summary
        == "Looks good."
    )


def test_rejecting_requires_feedback(tmp_path):
    app, project, projects = build(tmp_path)

    status, body = app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["reject"], "note": ["  "]},
    )

    assert status == 400
    assert "Feedback is required" in body
    assert (
        projects.load(project.id).deliverable("requirements").status
        is DeliverableStatus.AWAITING_APPROVAL
    )


def test_rejecting_with_feedback_sends_it_back(tmp_path):
    app, project, projects = build(tmp_path)

    status, _ = app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["reject"], "note": ["Add measurable outcomes."]},
    )

    assert status == 303

    stored = projects.load(project.id)

    assert stored.deliverable("requirements").status is (
        DeliverableStatus.CHANGES_REQUESTED
    )


def test_resume_runs_the_engagement(tmp_path):
    app, project, projects = build(tmp_path)

    app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["approve"], "note": ["Good."]},
    )

    status, _ = app.post(f"/engagement/{project.id}/resume", {})

    assert status == 303
    assert (
        projects.load(project.id).deliverable("curriculum").latest_version()
        is not None
    )


# ------------------------------------------------------------------- diff


def test_diff_shows_what_the_rework_changed(tmp_path):
    app, project, projects = build(tmp_path)

    app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["reject"], "note": ["Too thin."]},
    )
    app.post(f"/engagement/{project.id}/resume", {})

    status, body = app.get(
        f"/engagement/{project.id}/deliverable/requirements/diff", {}
    )

    assert status == 200
    assert "v1 → v2" in body
    assert "Why it was sent back" in body
    assert "Too thin." in body


def test_diff_needs_two_versions(tmp_path):
    app, project, _ = build(tmp_path)

    status, body = app.get(
        f"/engagement/{project.id}/deliverable/requirements/diff", {}
    )

    assert status == 404
    assert "only one version" in body


def test_a_specific_version_can_be_read(tmp_path):
    app, project, _ = build(tmp_path)

    app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["reject"], "note": ["Redo."]},
    )
    app.post(f"/engagement/{project.id}/resume", {})

    status, body = app.get(
        f"/engagement/{project.id}/deliverable/requirements",
        {"version": ["1"]},
    )

    assert status == 200
    assert "v1 of 2" in body


def test_an_unknown_version_is_a_404(tmp_path):
    app, project, _ = build(tmp_path)

    status, _ = app.get(
        f"/engagement/{project.id}/deliverable/requirements",
        {"version": ["99"]},
    )

    assert status == 404


@pytest.mark.parametrize(
    "path",
    ["/nope", "/engagement", "/engagement/x/y/z", "/../etc/passwd"],
)
def test_unknown_paths_do_not_raise(tmp_path, path):
    app, _, _ = build(tmp_path)

    status, _ = app.get(path, {})

    assert status == 404


# ------------------------------------------------------------- 2.0 stages


def test_the_engagement_page_names_the_methodology(tmp_path):
    app, project, _ = build(tmp_path)

    _, body = app.get(f"/engagement/{project.id}", {})

    assert "test-two-stage" in body


def test_stages_are_shown_with_their_gate_status(tmp_path):
    app, project, _ = build(tmp_path)

    _, body = app.get(f"/engagement/{project.id}", {})

    assert "Discovery" in body
    assert "gate not met" in body


def test_gate_failures_are_listed_not_just_flagged(tmp_path):
    app, project, _ = build(tmp_path)

    _, body = app.get(f"/engagement/{project.id}", {})

    assert "has not been approved" in body


def test_the_gate_shows_as_passed_once_approved(tmp_path):
    app, project, _ = build(tmp_path)

    app.post(
        f"/engagement/{project.id}/deliverable/requirements/review",
        {"decision": ["approve"], "note": ["Good."]},
    )

    _, body = app.get(f"/engagement/{project.id}", {})

    assert "gate passed" in body
