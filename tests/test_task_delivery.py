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


class _Answer(AgentProvider):
    def chat(self, messages, tools):
        return AgentTurn(content="done")


def _runner(tmp_path, deliver):
    def build(approver, stack, root):
        return AgentRunner(_Answer(), [], approver=approver)

    return WebTaskRunner(
        build,
        TaskRepository(tmp_path / "tasks"),
        "m",
        "sys",
        workspace=tmp_path,
        deliver=deliver,
    )


def test_serializer_round_trips_the_origin():
    serializer = TaskSerializer()
    record = TaskRecord(
        prompt="make a deck",
        origin={"type": "email", "message_id": "m1", "sender": "a@b.com"},
        notes=[Note("n")],
        history=[Exchange("p", "o")],
    )

    restored = serializer.from_dict(serializer.to_dict(record))

    assert restored.origin == {"type": "email", "message_id": "m1", "sender": "a@b.com"}


def test_a_task_from_an_email_is_delivered_to_its_origin_on_completion(tmp_path):
    delivered = []
    runner = _runner(tmp_path, deliver=lambda origin, folder: delivered.append(origin))

    origin = {"type": "email", "message_id": "m9", "sender": "c@acme.com"}
    task_id = runner.queue("prepare a deck", origin=origin)
    runner.pump()

    assert _wait(lambda: runner.view(task_id).status == "completed")
    assert _wait(lambda: delivered)
    assert delivered[0]["message_id"] == "m9"


def test_a_task_delivers_to_its_origin_only_once(tmp_path):
    delivered = []
    runner = _runner(tmp_path, deliver=lambda origin, files: delivered.append(origin))

    origin = {"type": "email", "message_id": "m1", "sender": "c@acme.com"}
    task_id = runner.queue("prepare a deck", origin=origin)
    runner.pump()
    assert _wait(lambda: len(delivered) == 1)

    # A re-run of the same task (as "Run again" or a follow-up does) must NOT
    # email the sender the deliverable a second time.
    runner.start("prepare a deck", task_id=task_id)
    assert _wait(lambda: runner.view(task_id).status == "completed")
    time.sleep(0.15)
    assert len(delivered) == 1


def test_a_task_without_an_origin_delivers_nothing(tmp_path):
    delivered = []
    runner = _runner(tmp_path, deliver=lambda origin, folder: delivered.append(origin))

    task_id = runner.start("just a task")

    assert _wait(lambda: runner.view(task_id).status == "completed")
    time.sleep(0.1)
    assert delivered == []
