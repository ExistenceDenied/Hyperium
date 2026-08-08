from __future__ import annotations

import time

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.interfaces.agent_provider import AgentProvider
from infrastructure.memory import MemoryStore
from infrastructure.notifications import NotificationStore
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.search_pages import snippet
from interfaces.web.server import ReviewApp
from interfaces.web.task_runner import WebTaskRunner


def _wait(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


class _Answer(AgentProvider):
    def chat(self, messages, tools):
        return AgentTurn(content="done")


def _app(tmp_path):
    def build(approver, stack, root):
        return AgentRunner(_Answer(), [], approver=approver)

    tasks = WebTaskRunner(
        build, TaskRepository(tmp_path / "tasks"), "m", "sys", workspace=tmp_path
    )
    memory = MemoryStore(tmp_path / "memory.json")
    notifications = NotificationStore(tmp_path / "n.json")
    app = ReviewApp(
        service=None,
        projects=None,
        tasks=tasks,
        memory=memory,
        notifications=notifications,
    )
    return app, tasks, memory, notifications


def test_snippet_centres_on_the_match():
    text = "The quarterly revenue figures look strong across every region."
    out = snippet(text, "revenue", width=30)
    assert "revenue" in out
    assert out.startswith("…") or out.startswith("The")


def test_empty_query_shows_the_prompt(tmp_path):
    app, *_ = _app(tmp_path)

    status, body = app.get("/search", {})

    assert status == 200
    assert "Find past tasks" in body


def test_search_finds_a_task_by_its_prompt(tmp_path):
    app, tasks, _, _ = _app(tmp_path)
    task_id = tasks.start("Draft a pricing proposal for Acme")
    assert _wait(lambda: tasks.view(task_id).status == "completed")

    status, body = app.get("/search", {"q": ["pricing"]})

    assert status == 200
    assert "Draft a pricing proposal for Acme" in body
    assert f"/tasks/{task_id}" in body


def test_search_finds_memory_and_alerts(tmp_path):
    app, _, memory, notifications = _app(tmp_path)
    memory.add("We invoice via Xero on net-30 terms", "finance")
    notifications.add("task", "Task finished: reconcile Xero", "/tasks/1")

    status, body = app.get("/search", {"q": ["xero"]})

    assert status == 200
    assert "net-30" in body
    assert "reconcile Xero" in body


def test_search_reports_when_nothing_matches(tmp_path):
    app, tasks, _, _ = _app(tmp_path)
    tasks.start("something unrelated")

    status, body = app.get("/search", {"q": ["zzznomatch"]})

    assert status == 200
    assert "Nothing matches" in body
