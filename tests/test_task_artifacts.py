from __future__ import annotations

from application.agent.task_service import deliverables_from
from core.agents.agent_result import AgentResult, AgentStep
from core.agents.task_record import TaskRecord
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.server import Download, ReviewApp
from interfaces.web.task_runner import WebTaskRunner


def test_deliverables_are_the_files_a_run_produced(tmp_path):
    steps = [
        AgentStep(tool="read_file", arguments={"path": "x.txt"}, result="..."),
        AgentStep(
            tool="write_file",
            arguments={"path": "out/report.md"},
            result="Wrote 10 characters to out/report.md.",
        ),
        AgentStep(
            tool="write_excel",
            arguments={"path": "quote.xlsx"},
            result="Wrote 2 rows to sheet 'Sheet1' in quote.xlsx.",
        ),
        AgentStep(
            tool="write_file",
            arguments={"path": "blocked.md"},
            result="Denied by the operator: the operator declined.",
        ),
    ]

    artifacts = deliverables_from(steps, tmp_path)

    assert str((tmp_path / "out" / "report.md").resolve()) in artifacts
    assert str((tmp_path / "quote.xlsx").resolve()) in artifacts
    # A read, and a denied write, are not deliverables.
    assert not any("x.txt" in a for a in artifacts)
    assert not any("blocked" in a for a in artifacts)


def test_a_produced_then_updated_file_is_listed_once(tmp_path):
    steps = [
        AgentStep(tool="write_excel", arguments={"path": "q.xlsx"}, result="Wrote..."),
        AgentStep(
            tool="update_excel_cell",
            arguments={"path": "q.xlsx"},
            result="Set B2 to '45' in q.xlsx.",
        ),
    ]

    assert len(deliverables_from(steps, tmp_path)) == 1


def test_the_record_persists_its_artifacts(tmp_path):
    repo = TaskRepository(tmp_path)
    record = TaskRecord(
        prompt="make a quote",
        result=AgentResult(output="done"),
        artifacts=[str(tmp_path / "quote.xlsx")],
    )

    repo.save(record)

    assert repo.get(record.id).artifacts == [str(tmp_path / "quote.xlsx")]


def test_the_web_serves_a_task_deliverable_for_download(tmp_path):
    produced = tmp_path / "quote.xlsx"
    produced.write_bytes(b"PK\x03\x04 not a real xlsx but bytes")

    repo = TaskRepository(tmp_path / "tasks")
    record = TaskRecord(
        prompt="quote",
        result=AgentResult(output="done"),
        artifacts=[str(produced)],
    )
    repo.save(record)

    runner = WebTaskRunner(lambda a, w, s: None, repo, "model", "system")
    app = ReviewApp(service=None, projects=None, tasks=runner)

    code, body = app.get(f"/tasks/{record.id}/deliverable/0", {})

    assert code == 200
    assert isinstance(body, Download)
    assert body.filename == "quote.xlsx"
    assert body.content == produced.read_bytes()
