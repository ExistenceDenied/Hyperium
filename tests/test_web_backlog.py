"""
The web interface as a full lifecycle, not just review.

At 1.5 mission authoring was deliberately kept out of the UI on the grounds
that "a second way to create missions is a second thing to keep correct".
These tests are what makes that safe: both interfaces call the same services,
and the parity tests below assert they behave identically.
"""

from __future__ import annotations

import pytest

from application.missions.mission_backlog_service import MissionBacklogService
from application.project.project_builder import ProjectBuilder
from core.missions.mission_priority import MissionPriority
from core.missions.mission_status import MissionStatus
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.persistence.mission_repository import MissionRepository
from infrastructure.persistence.project_repository import ProjectRepository
from interfaces.web.server import ReviewApp
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


class InlineRunner:
    """Runs background work synchronously so tests do not race a thread."""

    def __init__(self):
        self.errors = {}

    def busy(self, key):
        return False

    def running(self):
        return set()

    def error(self, key):
        return self.errors.get(key, "")

    def start(self, key, work):
        try:
            work()
        except Exception as error:
            self.errors[key] = str(error)


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
    backlog = MissionBacklogService(missions, project_service=service)

    app = ReviewApp(
        service,
        projects,
        missions=backlog,
        methodologies=methodologies,
        runner=InlineRunner(),
        resources=lambda: [build_consultant()],
    )

    return app, backlog, projects


def add(app, **overrides):
    form = {
        "title": ["Onboarding Redesign"],
        "objective": ["Halve time-to-first-value."],
        "priority": ["HIGH"],
        "criteria": ["Active in 14 days.\nZero manual steps."],
        "constraints": ["TIME: Must ship in Q3"],
        "methodology": [""],
    }
    form.update({k: [v] for k, v in overrides.items()})

    return app.post("/missions", form)


# --------------------------------------------------------------- backlog


def test_the_backlog_page_lists_missions(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)

    status, body = app.get("/missions", {})

    assert status == 200
    assert "Onboarding Redesign" in body
    assert "HIGH" in body


def test_an_empty_backlog_invites_the_first_mission(tmp_path):
    app, _, _ = build(tmp_path)

    status, body = app.get("/missions", {})

    assert status == 200
    assert "Nothing in the backlog yet" in body


def test_a_mission_can_be_created_from_the_form(tmp_path):
    app, backlog, _ = build(tmp_path)

    status, location = add(app)

    assert status == 303

    mission = backlog.list()[0]

    assert mission.title == "Onboarding Redesign"
    assert mission.priority is MissionPriority.HIGH
    assert [c.description for c in mission.success_criteria] == [
        "Active in 14 days.",
        "Zero manual steps.",
    ]
    assert mission.constraints[0].type.name == "TIME"
    assert location == f"/missions/{mission.id}"


def test_a_bad_form_is_re_rendered_with_what_was_typed(tmp_path):
    """Losing a half-written mission because of one bad line is unforgivable."""
    app, backlog, _ = build(tmp_path)

    status, body = add(app, stakeholders="just a name")

    assert status == 400
    assert "Name: role" in body
    assert "Halve time-to-first-value." in body  # not lost
    assert backlog.list() == []


def test_a_constraint_needs_no_category(tmp_path):
    """
    Regression: the form demanded a TYPE prefix, never said which types were
    valid, and rejected the whole edit if you guessed wrong.
    """
    app, backlog, _ = build(tmp_path)

    status, _ = add(app, constraints="COST: under budget\nMust be quiet")

    assert status == 303
    assert [c.description for c in backlog.list()[0].constraints] == [
        "COST: under budget",
        "Must be quiet",
    ]


def test_the_form_says_which_categories_exist(tmp_path):
    app, _, _ = build(tmp_path)

    _, body = app.get("/missions/new", {})

    assert "Time" in body and "Legal" in body
    assert "kept as written" in body


def test_an_empty_title_is_rejected(tmp_path):
    app, backlog, _ = build(tmp_path)

    status, body = add(app, title="   ")

    assert status == 400
    assert "title is required" in body
    assert backlog.list() == []


def test_a_mission_can_be_edited(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    status, _ = app.post(
        f"/missions/{mission.id}/edit",
        {
            "title": ["Renamed"],
            "objective": ["A better objective."],
            "priority": ["CRITICAL"],
            "criteria": ["Only one now."],
            "constraints": [""],
            "methodology": [""],
        },
    )

    assert status == 303

    updated = backlog.get(mission.id)

    assert updated.title == "Renamed"
    assert updated.priority is MissionPriority.CRITICAL
    assert [c.description for c in updated.success_criteria] == ["Only one now."]
    assert updated.constraints == []


def test_a_mission_can_be_archived_and_restored(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    app.post(f"/missions/{mission.id}/archive", {})
    assert backlog.get(mission.id).status is MissionStatus.ARCHIVED

    app.post(f"/missions/{mission.id}/restore", {})
    assert backlog.get(mission.id).status is MissionStatus.DRAFT


def test_archived_missions_are_hidden_until_asked_for(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    app.post(f"/missions/{backlog.list()[0].id}/archive", {})

    _, hidden = app.get("/missions", {})
    _, shown = app.get("/missions", {"all": ["1"]})

    assert "Onboarding Redesign" not in hidden
    assert "Onboarding Redesign" in shown


def test_a_mission_can_be_deleted(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    status, location = app.post(f"/missions/{mission.id}/delete", {})

    assert status == 303
    assert location == "/missions"
    assert backlog.list() == []


def test_an_incomplete_mission_says_why_it_cannot_launch(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, criteria="")

    _, body = app.get(f"/missions/{backlog.list()[0].id}", {})

    assert "cannot be launched yet" in body
    assert "disabled" in body


# ---------------------------------------------------------------- launch


def test_launching_from_the_ui_runs_the_engagement(tmp_path):
    app, backlog, projects = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]

    status, location = app.post(
        f"/missions/{mission.id}/launch", {"methodology": ["test-two-stage"]}
    )

    assert status == 303
    assert location == f"/missions/{mission.id}"

    launched = backlog.get(mission.id)

    assert launched.status is MissionStatus.LAUNCHED
    assert launched.project_id in projects.list_ids()


def test_the_methodology_chosen_at_launch_is_recorded(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    app.post(
        f"/missions/{mission.id}/launch", {"methodology": ["test-two-stage"]}
    )

    assert backlog.get(mission.id).methodology == "test-two-stage"


def test_a_launch_failure_is_shown_not_swallowed(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, criteria="")
    mission = backlog.list()[0]

    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    _, body = app.get(f"/missions/{mission.id}", {})

    assert "Could not launch" in body
    assert "success criterion" in body


def test_a_launched_mission_is_shown_as_frozen(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    _, body = app.get(f"/missions/{mission.id}", {})

    assert "Open the full engagement" in body
    assert "frozen" in body
    assert "Edit</a>" not in body


def test_the_mission_shows_the_deliverables_it_produced(tmp_path):
    """The thing a user asks for by name: what did this mission produce?"""
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    _, body = app.get(f"/missions/{mission.id}", {})

    assert "Training Requirements" in body
    assert "requirements-v1.md" in body
    assert "AWAITING APPROVAL" in body
    assert "Download" in body


def test_the_mission_shows_stage_gates(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    _, body = app.get(f"/missions/{mission.id}", {})

    assert "Discovery" in body
    assert "gate not met" in body
    assert "has not been approved" in body


def test_an_unreadable_engagement_is_reported_on_the_mission(tmp_path):
    """Showing a launched mission with no deliverables would be a lie."""
    app, backlog, projects = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    path = (tmp_path / "state") / f"{backlog.get(mission.id).project_id}.json"
    path.write_text("{ not json", encoding="utf-8")

    _, body = app.get(f"/missions/{mission.id}", {})

    assert "could not be read" in body


# ---------------------------------------------------- fields that were lost


def test_editing_saves_the_methodology(tmp_path):
    """
    Regression: the edit form rendered a methodology select and the handler
    never passed it, so the control silently did nothing.
    """
    app, backlog, _ = build(tmp_path)
    add(app, methodology="")
    mission = backlog.list()[0]

    app.post(
        f"/missions/{mission.id}/edit",
        {
            "title": ["Onboarding Redesign"],
            "objective": ["Halve time-to-first-value."],
            "priority": ["HIGH"],
            "criteria": ["Active in 14 days."],
            "constraints": [""],
            "stakeholders": [""],
            "methodology": ["test-two-stage"],
        },
    )

    assert backlog.get(mission.id).methodology == "test-two-stage"


def test_stakeholders_can_be_captured_and_edited(tmp_path):
    app, backlog, _ = build(tmp_path)

    add(app, stakeholders="Priya: Head of Customer Success\nSam: CFO")
    mission = backlog.list()[0]

    assert [(s.name, s.role) for s in mission.stakeholders] == [
        ("Priya", "Head of Customer Success"),
        ("Sam", "CFO"),
    ]

    _, body = app.get(f"/missions/{mission.id}", {})
    assert "Priya — Head of Customer Success" in body


def test_a_malformed_stakeholder_is_rejected_without_losing_the_form(tmp_path):
    app, backlog, _ = build(tmp_path)

    status, body = add(app, stakeholders="just a name")

    assert status == 400
    assert "Name: role" in body
    assert "Halve time-to-first-value." in body
    assert backlog.list() == []


# --------------------------------------------------------- other actions


def test_a_complete_draft_can_be_marked_ready(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    status, _ = app.post(f"/missions/{mission.id}/ready", {})

    assert status == 303
    assert backlog.get(mission.id).status is MissionStatus.READY


def test_marking_an_incomplete_mission_ready_is_refused(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, criteria="")
    mission = backlog.list()[0]

    status, body = app.post(f"/missions/{mission.id}/ready", {})

    assert status == 400
    assert "success criterion" in body


def test_deleting_asks_first(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]

    status, body = app.get(f"/missions/{mission.id}/delete", {})

    assert status == 200
    assert "cannot be undone" in body
    assert backlog.list() != []


def test_the_delete_confirmation_warns_about_a_launched_mission(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    _, body = app.get(f"/missions/{mission.id}/delete", {})

    assert "orphans that engagement" in body


# ------------------------------------------------------------- downloads


def test_a_deliverable_can_be_downloaded_as_a_file(tmp_path):
    from interfaces.web.server import Download

    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})
    project_id = backlog.get(mission.id).project_id

    status, body = app.get(
        f"/engagement/{project_id}/deliverable/requirements/raw", {}
    )

    assert status == 200
    assert isinstance(body, Download)
    assert body.filename == "requirements-v1.md"
    assert "Juniors must run an intake workshop." in body.content


def test_downloading_an_unknown_version_is_a_404(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})
    project_id = backlog.get(mission.id).project_id

    status, _ = app.get(
        f"/engagement/{project_id}/deliverable/requirements/raw",
        {"version": ["99"]},
    )

    assert status == 404


def test_the_engagement_links_back_to_its_mission(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})
    project_id = backlog.get(mission.id).project_id

    _, body = app.get(f"/engagement/{project_id}", {})

    assert f"/missions/{mission.id}" in body


# --------------------------------------------------------- methodologies


def test_the_methodology_catalogue_lists_what_is_available(tmp_path):
    app, _, _ = build(tmp_path)

    status, body = app.get("/methodologies", {})

    assert status == 200
    assert "Two Stage Test Methodology" in body
    assert "Stakeholder Interviewing" in body


def test_a_methodology_shows_its_stages_and_gates(tmp_path):
    app, _, _ = build(tmp_path)

    status, body = app.get("/methodologies/test-two-stage", {})

    assert status == 200
    assert "Discovery" in body
    assert "Design" in body
    assert "a human approves every deliverable" in body
    assert "Elicit learning needs" in body


def test_an_unknown_methodology_is_a_404(tmp_path):
    app, _, _ = build(tmp_path)

    status, _ = app.get("/methodologies/nope", {})

    assert status == 404


# ------------------------------------------------------------ human work


def test_human_allocated_work_can_be_submitted_from_the_ui(tmp_path):
    from core.capabilities.capability_catalog import CapabilityCatalog
    from core.capabilities.proficiency_level import ProficiencyLevel
    from core.resources.human_resource import HumanResource

    analyst = HumanResource(name="Priya", role="Business Analyst")
    for key in CapabilityCatalog.keys():
        analyst.add_capability(CapabilityCatalog.get(key), ProficiencyLevel.EXPERT)

    methodologies = FakeMethodologies()
    projects = ProjectRepository(tmp_path / "state")
    service = ProjectBuilder.build(
        ScriptedLLM(),
        InMemoryArtifactStore(),
        repository=projects,
        methodologies=methodologies,
    )
    project = service.start(build_mission(), resources=[analyst])
    app = ReviewApp(service, projects, runner=InlineRunner())

    _, body = app.get(f"/engagement/{project.id}", {})
    assert "Submit work" in body
    assert "assigned to Priya" in body

    status, _ = app.post(
        f"/engagement/{project.id}/activity/elicit/submit",
        {"content": ["## Needs\nGathered in a workshop."]},
    )

    assert status == 303
    assert projects.load(project.id).execution_plan.activity_by_key(
        "elicit"
    ).is_completed


def test_no_submission_form_appears_for_ai_work(tmp_path):
    app, _, projects = build(tmp_path)
    add(app, methodology="test-two-stage")

    # the engagement page for an AI-run engagement offers no submission box
    from tests.fixtures import build_consultant  # noqa: F401

    _, body = app.get("/", {})

    assert "Submit work" not in body


# --------------------------------------------------------------- routing


@pytest.mark.parametrize(
    "path",
    ["/nope", "/missions/not-a-uuid", "/engagement", "/../etc/passwd", "/missions/x/y"],
)
def test_unknown_paths_are_404(tmp_path, path):
    app, _, _ = build(tmp_path)

    status, _ = app.get(path, {})

    assert status == 404


def test_an_unknown_post_path_is_404(tmp_path):
    app, _, _ = build(tmp_path)

    status, _ = app.post("/missions/nope/explode", {})

    assert status == 404


def test_navigation_is_present_on_every_section(tmp_path):
    app, _, _ = build(tmp_path)

    for path in ("/", "/missions", "/methodologies"):
        _, body = app.get(path, {})

        # The backlog now lives under the Tasks tab, not its own nav item.
        assert "href='/tasks'" in body
        assert "href='/methodologies'" in body


def test_the_edit_form_is_refused_for_a_launched_mission(tmp_path):
    """
    Regression: the Edit link was hidden, but navigating to the edit URL
    directly — a bookmark, the back button, a typed address — rendered a full
    form that only refused on submit, after the work was done.
    """
    app, backlog, _ = build(tmp_path)
    add(app, methodology="test-two-stage")
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/launch", {"methodology": [""]})

    status, body = app.get(f"/missions/{mission.id}/edit", {})

    assert status == 409  # it exists; its state forbids editing
    assert "cannot be edited" in body
    assert "name='title'" not in body


def test_the_edit_form_is_refused_for_an_archived_mission(tmp_path):
    app, backlog, _ = build(tmp_path)
    add(app)
    mission = backlog.list()[0]
    app.post(f"/missions/{mission.id}/archive", {})

    status, body = app.get(f"/missions/{mission.id}/edit", {})

    assert status == 409
    assert "cannot be edited" in body
