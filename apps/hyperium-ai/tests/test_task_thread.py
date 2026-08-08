from __future__ import annotations

import time

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.agents.task_record import Exchange, Note, TaskRecord
from core.interfaces.agent_provider import AgentProvider
from infrastructure.persistence.task_repository import TaskRepository
from infrastructure.persistence.task_serializer import TaskSerializer
from interfaces.web.task_runner import WebTaskRunner


def _wait(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


class _Echo(AgentProvider):
    """Answers with the prompt it saw, so we can assert on the context given."""

    def __init__(self):
        self.prompts = []

    def chat(self, messages, tools):
        user = next(m["content"] for m in messages if m["role"] == "user")
        self.prompts.append(user)
        return AgentTurn(content=f"answer to: {user[:20]}")


def _runner(tmp_path, provider):
    def build(approver, stack, root):
        return AgentRunner(provider, [], approver=approver)

    repo = TaskRepository(tmp_path / "tasks")
    runner = WebTaskRunner(build, repo, "m", "sys", workspace=tmp_path)
    return runner, repo


def test_serializer_round_trips_the_thread(tmp_path):
    serializer = TaskSerializer()
    record = TaskRecord(
        prompt="make it shorter",
        notes=[Note(text="a note")],
        history=[Exchange(prompt="write a bio", output="a long bio")],
    )

    restored = serializer.from_dict(serializer.to_dict(record))

    assert len(restored.history) == 1
    assert restored.history[0].prompt == "write a bio"
    assert restored.history[0].output == "a long bio"


def test_a_reply_keeps_the_prior_turn_and_feeds_it_as_context(tmp_path):
    provider = _Echo()
    runner, repo = _runner(tmp_path, provider)

    task_id = runner.start("write a short bio")
    assert _wait(lambda: runner.view(task_id).status == "completed")

    runner.follow_up(task_id, "now make it shorter")
    assert _wait(
        lambda: runner.view(task_id).prompt == "now make it shorter"
        and runner.view(task_id).status == "completed"
    )

    # The finished record carries the earlier turn as history...
    view = runner.view(task_id)
    assert len(view.history) == 1
    assert view.history[0].prompt == "write a short bio"

    # ...and the follow-up run was actually given that turn as context.
    assert any(
        "write a short bio" in prompt and "make it shorter" in prompt
        for prompt in provider.prompts
    )


def test_replying_to_an_unknown_task_is_a_no_op(tmp_path):
    from uuid import uuid4

    provider = _Echo()
    runner, _ = _runner(tmp_path, provider)

    runner.follow_up(uuid4(), "hello?")  # must not raise

    assert provider.prompts == []
