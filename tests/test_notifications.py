from __future__ import annotations

import json
import time

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.interfaces.agent_provider import AgentProvider
from infrastructure.notifications import NotificationStore
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.server import ReviewApp
from interfaces.web.task_runner import WebTaskRunner


def _wait(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_store_adds_lists_and_marks_read(tmp_path):
    store = NotificationStore(tmp_path / "n.json")

    store.add("task", "Task finished: report", "/tasks/1")
    second = store.add("approval", "A task needs approval", "/tasks/2")

    notes = store.list()
    assert [n.text for n in notes] == [  # newest first
        "A task needs approval",
        "Task finished: report",
    ]
    assert store.unread_count() == 2

    store.mark_read(second.id)
    assert store.unread_count() == 1

    store.mark_all_read()
    assert store.unread_count() == 0


def test_unread_json_endpoint_reports_count_and_items(tmp_path):
    store = NotificationStore(tmp_path / "n.json")
    store.add("task", "Task finished: quote", "/tasks/9")

    app = ReviewApp(service=None, projects=None, notifications=store)

    status, body = app.get("/notifications/unread.json", {})

    assert status == 200
    payload = json.loads(body)
    assert payload["count"] == 1
    assert payload["items"][0]["text"] == "Task finished: quote"
    assert payload["items"][0]["link"] == "/tasks/9"


def test_marking_all_read_from_the_web_clears_the_count(tmp_path):
    store = NotificationStore(tmp_path / "n.json")
    store.add("task", "one", "")
    store.add("task", "two", "")

    app = ReviewApp(service=None, projects=None, notifications=store)

    status, location = app.post("/notifications/read", {})

    assert status == 303
    assert location == "/notifications"
    assert store.unread_count() == 0


def test_dashboard_is_the_home_page_and_shows_alerts(tmp_path):
    store = NotificationStore(tmp_path / "n.json")
    store.add("task", "Task finished: audit", "/tasks/3")

    app = ReviewApp(service=None, projects=None, notifications=store)

    status, body = app.get("/", {})

    assert status == 200
    assert "Dashboard" in body
    assert "Task finished: audit" in body


def test_finishing_a_task_records_an_alert(tmp_path):
    store = NotificationStore(tmp_path / "n.json")

    class _Answer(AgentProvider):
        def chat(self, messages, tools):
            return AgentTurn(content="done")

    def build(approver, stack, root):
        return AgentRunner(_Answer(), [], approver=approver)

    runner = WebTaskRunner(
        build,
        TaskRepository(tmp_path / "tasks"),
        "m",
        "sys",
        workspace=tmp_path,
        notify=store.add,
    )

    task_id = runner.start("write a report")

    assert _wait(lambda: store.unread_count() >= 1)
    note = store.list()[0]
    assert "Task finished" in note.text
    assert note.link == f"/tasks/{task_id}"
