"""
CLI coverage using a fake provider, so the human-in-the-loop flow is tested
without a live model.
"""

import interfaces.cli as cli
from config.settings import Settings
from core.execution.execution_result import ExecutionStatus
from infrastructure.artifacts.file_artifact_store import FileArtifactStore
from infrastructure.persistence.project_repository import ProjectRepository
from tests.fixtures import FakeMethodologies, ScriptedLLM


def install_fake_context(monkeypatch, tmp_path):
    """
    Swap the Ollama-backed provider for a scripted one, and point every path
    at tmp_path so a test never writes into the real workspace.
    """
    from application.project.project_builder import ProjectBuilder

    settings = Settings(
        workspace=tmp_path / "workspace",
        state_directory=tmp_path / "state",
        log_file=tmp_path / "hyperium.log",
    )

    repository = ProjectRepository(settings.state_directory)
    store = FileArtifactStore(settings.workspace)

    def build_context(_settings):
        service = ProjectBuilder.build(
            ScriptedLLM(),
            store,
            repository=repository,
            methodologies=FakeMethodologies(),
        )
        return service, repository

    monkeypatch.setattr(cli, "build_context", build_context)
    monkeypatch.setattr(Settings, "load", classmethod(lambda cls: settings))
    monkeypatch.setattr(cli, "configure_logging", lambda *a, **k: None)

    return repository, settings.workspace


def run(argv):
    return cli.main(argv)


def test_run_starts_an_engagement_and_stops_at_the_gate(
    monkeypatch, tmp_path, capsys
):
    repository, workspace = install_fake_context(monkeypatch, tmp_path)

    assert run(["run", "BA Training", "Build a one-day training."]) == 0

    output = capsys.readouterr().out

    assert "AWAITING_APPROVAL" in output
    assert "Awaiting your review" in output

    project = repository.load(repository.list_ids()[0])

    assert project.execution_result.status is ExecutionStatus.AWAITING_APPROVAL
    assert (workspace / "requirements-v1.md").exists()


def test_approve_then_resume_advances_the_engagement(
    monkeypatch, tmp_path, capsys
):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    project_id = str(repository.list_ids()[0])
    capsys.readouterr()

    assert run(["approve", project_id, "requirements", "--note", "Good."]) == 0
    assert "approved" in capsys.readouterr().out

    assert run(["resume", project_id]) == 0
    capsys.readouterr()

    project = repository.load(repository.list_ids()[0])

    assert project.deliverable("requirements").is_approved
    assert project.deliverable("curriculum").latest_version() is not None


def test_reject_records_the_note_and_does_not_advance(
    monkeypatch, tmp_path, capsys
):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    project_id = str(repository.list_ids()[0])
    capsys.readouterr()

    assert run(["reject", project_id, "requirements", "--note", "Too thin."]) == 0

    project = repository.load(repository.list_ids()[0])
    requirements = project.deliverable("requirements")

    assert not requirements.is_approved
    assert requirements.latest_version().review_summary == "Too thin."
    assert project.deliverable("curriculum").latest_version() is None


def test_list_shows_saved_engagements(monkeypatch, tmp_path, capsys):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    capsys.readouterr()

    assert run(["list"]) == 0

    output = capsys.readouterr().out

    assert str(repository.list_ids()[0]) in output
    assert "BA Training" in output


def test_show_prints_deliverable_content(monkeypatch, tmp_path, capsys):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    project_id = str(repository.list_ids()[0])
    capsys.readouterr()

    assert run(["show", project_id, "requirements"]) == 0

    assert "Juniors must run an intake workshop." in capsys.readouterr().out


def test_unknown_deliverable_exits_non_zero(monkeypatch, tmp_path, capsys):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    project_id = str(repository.list_ids()[0])
    capsys.readouterr()

    assert run(["approve", project_id, "nope"]) == 1
    assert "No deliverable" in capsys.readouterr().err


# ------------------------------------------------------- mission backlog


def mission_ids(monkeypatch, tmp_path):
    from infrastructure.persistence.mission_repository import MissionRepository

    return MissionRepository((tmp_path / "state") / "missions")


def test_mission_add_puts_a_draft_in_the_backlog(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    assert run(
        [
            "mission", "add", "Onboarding Redesign",
            "Cut time-to-first-value in half.",
            "--priority", "high",
            "--criterion", "Time halved.",
            "--constraint", "TIME:Must ship in Q3",
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "DRAFT" in output
    assert "HIGH" in output
    assert "Must ship in Q3" in output

    missions = mission_ids(monkeypatch, tmp_path).list()
    assert [m.title for m in missions] == ["Onboarding Redesign"]


def test_mission_add_accepts_an_incomplete_draft(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    assert run(["mission", "add", "Half an idea", "Something vague."]) == 0
    assert "incomplete" in capsys.readouterr().out


def test_mission_list_is_ordered_by_priority(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Low one", "obj", "--priority", "low"])
    run(["mission", "add", "Critical one", "obj", "--priority", "critical"])
    capsys.readouterr()

    assert run(["mission", "list"]) == 0

    lines = [ln for ln in capsys.readouterr().out.splitlines() if "one" in ln]

    assert "Critical one" in lines[0]
    assert "Low one" in lines[1]


def test_mission_edit_refines_a_draft(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Draft", "obj"])
    mission_id = str(mission_ids(monkeypatch, tmp_path).list()[0].id)
    capsys.readouterr()

    assert run(
        [
            "mission", "edit", mission_id,
            "--title", "Refined",
            "--add-criterion", "It works.",
            "--priority", "critical",
        ]
    ) == 0

    output = capsys.readouterr().out

    assert "Refined" in output
    assert "CRITICAL" in output
    assert "incomplete" not in output


def test_mission_delete_removes_it(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Doomed", "obj"])
    mission_id = str(mission_ids(monkeypatch, tmp_path).list()[0].id)
    capsys.readouterr()

    assert run(["mission", "delete", mission_id]) == 0
    assert "Deleted mission 'Doomed'" in capsys.readouterr().out
    assert mission_ids(monkeypatch, tmp_path).list() == []


def test_launch_runs_a_backlog_mission(monkeypatch, tmp_path, capsys):
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Onboarding", "obj", "--criterion", "Done."])
    mission_id = str(mission_ids(monkeypatch, tmp_path).list()[0].id)
    capsys.readouterr()

    assert run(["launch", mission_id]) == 0
    assert "AWAITING_APPROVAL" in capsys.readouterr().out

    mission = mission_ids(monkeypatch, tmp_path).get(
        mission_ids(monkeypatch, tmp_path).list()[0].id
    )

    assert mission.status.value == "LAUNCHED"
    assert mission.project_id == repository.list_ids()[0]


def test_launching_an_incomplete_mission_exits_non_zero(
    monkeypatch, tmp_path, capsys
):
    install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Vague", "obj"])
    mission_id = str(mission_ids(monkeypatch, tmp_path).list()[0].id)
    capsys.readouterr()

    assert run(["launch", mission_id]) == 1
    assert "success criterion" in capsys.readouterr().err


def test_deleting_a_launched_mission_exits_non_zero(
    monkeypatch, tmp_path, capsys
):
    install_fake_context(monkeypatch, tmp_path)

    run(["mission", "add", "Onboarding", "obj", "--criterion", "Done."])
    mission_id = str(mission_ids(monkeypatch, tmp_path).list()[0].id)
    run(["launch", mission_id])
    capsys.readouterr()

    assert run(["mission", "delete", mission_id]) == 1
    assert "orphans that engagement" in capsys.readouterr().err

    assert run(["mission", "delete", mission_id, "--force"]) == 0


def test_run_shortcut_still_records_the_mission(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    assert run(["run", "Ad hoc", "Do the thing."]) == 0
    capsys.readouterr()

    missions = mission_ids(monkeypatch, tmp_path).list()

    assert [m.title for m in missions] == ["Ad hoc"]
    assert missions[0].status.value == "LAUNCHED"


def test_a_malformed_constraint_is_rejected(monkeypatch, tmp_path, capsys):
    install_fake_context(monkeypatch, tmp_path)

    assert run(
        ["mission", "add", "X", "obj", "--constraint", "no-colon-here"]
    ) == 1
    assert "type:description" in capsys.readouterr().err


def test_cli_reject_now_requires_feedback_like_the_web(monkeypatch, tmp_path, capsys):
    """
    Regression: approval logic lived in both adapters and they drifted — the
    web required feedback on rejection and the CLI did not. Both now call
    ProjectService, so they cannot disagree.
    """
    repository, _ = install_fake_context(monkeypatch, tmp_path)

    run(["run", "BA Training", "Build a one-day training."])
    project_id = str(repository.list_ids()[0])
    capsys.readouterr()

    assert run(["reject", project_id, "requirements"]) == 1
    assert "Feedback is required" in capsys.readouterr().err

    project = repository.load(repository.list_ids()[0])
    assert not project.deliverable("requirements").is_approved
