from __future__ import annotations

from application.agent.agent_runner import AgentRunner
from core.agents.agent_turn import AgentTurn
from core.interfaces.agent_provider import AgentProvider
from infrastructure.memory import MemoryStore
from interfaces.web.server import ReviewApp
from interfaces.web.task_runner import WebTaskRunner


def test_memory_crud_and_context(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")

    day_rate = store.add("Our day rate is 600 GBP.", "pricing")
    store.add("We are warm and plain-speaking.", "voice")

    assert len(store.list()) == 2

    context = store.as_context()
    assert "600 GBP" in context
    assert "pricing" in context
    assert "voice" in context

    store.update(day_rate.id, "Our day rate is 650 GBP.", "pricing")
    assert "650 GBP" in store.as_context()

    store.delete(day_rate.id)
    assert len(store.list()) == 1


def test_empty_memory_yields_no_context(tmp_path):
    assert MemoryStore(tmp_path / "memory.json").as_context() == ""


class _RecordingAnswer(AgentProvider):
    def __init__(self):
        self.prompts = []

    def chat(self, messages, tools):
        for message in messages:
            if message.get("role") == "user":
                self.prompts.append(message["content"])
        return AgentTurn(content="done")


def _wait(condition, timeout=5.0):
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


def test_memory_is_injected_into_a_task(tmp_path):
    from infrastructure.persistence.task_repository import TaskRepository

    store = MemoryStore(tmp_path / "memory.json")
    store.add("Our day rate is 600 GBP.", "pricing")

    provider = _RecordingAnswer()

    def build(approver, stack, root):
        return AgentRunner(provider, [], approver=approver)

    runner = WebTaskRunner(
        build,
        TaskRepository(tmp_path / "tasks"),
        "m",
        "sys",
        workspace=tmp_path,
        context=store.as_context,
    )

    task_id = runner.start("draft a quote")
    assert _wait(lambda: runner.view(task_id).status == "completed")

    assert any("600 GBP" in prompt for prompt in provider.prompts)


def test_web_memory_routes(tmp_path):
    store = MemoryStore(tmp_path / "memory.json")
    app = ReviewApp(service=None, projects=None, memory=store)

    code, redirect = app.post(
        "/memory", {"text": ["Our day rate is 600 GBP."], "category": ["pricing"]}
    )
    assert code == 303 and redirect == "/memory"
    assert len(store.list()) == 1

    code, body = app.get("/memory", {})
    assert code == 200 and "600 GBP" in body

    entry = store.list()[0]
    code, _ = app.post(f"/memory/{entry.id}/delete", {})
    assert code == 303
    assert store.list() == []
