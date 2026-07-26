from __future__ import annotations

import threading
import time

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.agents.approval import ActionRequest
from core.agents.tool_call import ToolCall
from core.interfaces.agent_provider import AgentProvider
from core.tools.tool import Tool
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.server import ReviewApp
from interfaces.web.task_runner import WebApprover, WebTaskRunner


def _wait(condition, timeout: float = 5.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


# ------------------------------------------------------------- WebApprover


def test_web_approver_blocks_until_resolved():
    approver = WebApprover()
    decisions = []

    def ask():
        decisions.append(
            approver.review(ActionRequest("write", {}, "write a file"))
        )

    thread = threading.Thread(target=ask)
    thread.start()

    assert _wait(lambda: approver.pending() is not None)
    assert not decisions  # still blocked

    approver.resolve(approved=True)
    thread.join(timeout=2)

    assert decisions[0].approved is True


# --------------------------------------------------- an acting fake agent


class ActTool(Tool):
    name = "act"
    description = "Change something."
    parameters = {"type": "object", "properties": {}}
    requires_approval = True

    def invoke(self, arguments):
        return "acted"


class ApprovalThenAnswer(AgentProvider):
    """Asks to run the acting tool once, then answers."""

    def __init__(self):
        self.calls = 0

    def chat(self, messages, tools):
        self.calls += 1
        if self.calls == 1:
            return AgentTurn(tool_calls=[ToolCall(name="act", arguments={})])
        return AgentTurn(content="finished")


def _runner(repo):
    provider = ApprovalThenAnswer()

    def build(approver, allow_writes, stack):
        return AgentRunner(provider, [ActTool()], approver=approver)

    return WebTaskRunner(build, repo, model="test", system="do the task")


# --------------------------------------------------- runner lifecycle


def test_task_waits_for_approval_then_completes_and_persists(tmp_path):
    repo = TaskRepository(tmp_path)
    runner = _runner(repo)

    task_id = runner.start("act on it", allow_writes=True)

    assert _wait(
        lambda: (runner.view(task_id).status == "awaiting approval")
    )

    runner.approve(task_id, approved=True)

    assert _wait(lambda: runner.view(task_id).status == "completed")
    assert repo.get(task_id).prompt == "act on it"


def test_rejection_is_reported_and_nothing_acts(tmp_path):
    repo = TaskRepository(tmp_path)
    runner = _runner(repo)

    task_id = runner.start("act on it", allow_writes=True)
    assert _wait(lambda: runner.view(task_id).status == "awaiting approval")

    runner.approve(task_id, approved=False)
    assert _wait(lambda: runner.view(task_id).status == "completed")

    steps = runner.view(task_id).steps
    assert any("Denied by the operator" in step.result for step in steps)


# ----------------------------------------------------------- the routes


def _app(repo):
    return ReviewApp(service=None, projects=None, tasks=_runner(repo))


def test_index_is_empty_then_lists_a_started_task(tmp_path):
    app = _app(TaskRepository(tmp_path))

    code, body = app.get("/tasks", {})
    assert code == 200 and "No tasks yet" in body

    code, redirect = app.post("/tasks", {"prompt": ["do it"], "allow_writes": ["1"]})
    assert code == 303 and redirect.startswith("/tasks/")


def test_detail_shows_approval_then_the_result(tmp_path):
    app = _app(TaskRepository(tmp_path))

    _, redirect = app.post("/tasks", {"prompt": ["do it"], "allow_writes": ["1"]})
    task_id = redirect.rsplit("/", 1)[1]

    assert _wait(lambda: "Approval needed" in app.get(f"/tasks/{task_id}", {})[1])

    code, redirect = app.post(f"/tasks/{task_id}/approve", {"decision": ["approve"]})
    assert code == 303

    assert _wait(lambda: "Result" in app.get(f"/tasks/{task_id}", {})[1])


def test_new_task_form_renders(tmp_path):
    app = _app(TaskRepository(tmp_path))

    code, body = app.get("/tasks/new", {})

    assert code == 200
    assert "<textarea name='prompt'" in body
