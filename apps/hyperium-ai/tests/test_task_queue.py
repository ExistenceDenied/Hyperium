from __future__ import annotations

import time

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.interfaces.agent_provider import AgentProvider
from infrastructure.persistence.task_repository import TaskRepository
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


def _runner(tmp_path, reviewer=None, max_concurrent=1):
    provider = _Answer()

    def build(approver, stack, root):
        return AgentRunner(provider, [], approver=approver)

    repo = TaskRepository(tmp_path / "tasks")
    runner = WebTaskRunner(
        build,
        repo,
        "m",
        "sys",
        workspace=tmp_path,
        reviewer=reviewer,
        max_concurrent=max_concurrent,
    )
    return runner, repo


def test_a_queued_task_is_not_started_until_pumped(tmp_path):
    runner, repo = _runner(tmp_path)

    task_id = runner.queue("do it later", priority="high")

    assert repo.get(task_id).queued is True
    assert runner.view(task_id).status == "queued"

    runner.pump()

    assert _wait(lambda: runner.view(task_id).status == "completed")
    assert repo.get(task_id).queued is False


def test_pump_respects_the_concurrency_limit(tmp_path):
    # A provider that blocks so tasks stay running.
    class Block(AgentProvider):
        def __init__(self):
            self.event = __import__("threading").Event()

        def chat(self, messages, tools):
            self.event.wait(2)
            return AgentTurn(content="done")

    provider = Block()

    def build(approver, stack, root):
        return AgentRunner(provider, [], approver=approver)

    repo = TaskRepository(tmp_path / "tasks")
    runner = WebTaskRunner(build, repo, "m", "s", workspace=tmp_path, max_concurrent=1)

    a = runner.queue("first")
    b = runner.queue("second")

    runner.pump()  # should start only one

    running = [
        tid for tid in (a, b) if runner.view(tid).status in ("running", "pending")
    ]
    assert len(running) == 1
    assert any(runner.view(tid).status == "queued" for tid in (a, b))

    provider.event.set()


def test_reviewer_queues_improvement_tasks(tmp_path):
    def reviewer(prompt, output):
        return ["Add a summary section", "Check the figures"]

    runner, repo = _runner(tmp_path, reviewer=reviewer)

    done = runner.start("write a report")
    assert _wait(lambda: runner.view(done).status == "completed")

    runner.suggest_improvements(done)

    assert _wait(lambda: len(repo.list()) >= 3)  # the original + two improvements
    prompts = {record.prompt for record in repo.list()}
    assert "Add a summary section" in prompts
    assert any(record.queued for record in repo.list())
