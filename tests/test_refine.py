from __future__ import annotations

import time

from application.agent.quality_critic import QualityCritic
from core.agents.agent_result import AgentResult, AgentStep, StopReason
from core.interfaces.llm_provider import LLMProvider
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.task_runner import WebTaskRunner


def _wait(condition, timeout=5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


# ------------------------------------------------------------- the critic


class _LLM(LLMProvider):
    def __init__(self, response):
        self.response = response

    def generate(self, prompt):
        return self.response


def test_critic_returns_feedback_when_not_good_enough():
    critic = QualityCritic(
        _LLM('{"good_enough": false, "feedback": "Add concrete figures."}')
    )
    assert critic.critique("make a deck", "thin content") == "Add concrete figures."


def test_critic_returns_empty_when_good_enough():
    critic = QualityCritic(_LLM('{"good_enough": true, "feedback": ""}'))
    assert critic.critique("make a deck", "great content") == ""


def test_critic_ignores_empty_content():
    critic = QualityCritic(_LLM('{"good_enough": false, "feedback": "x"}'))
    assert critic.critique("t", "   ") == ""


# ------------------------------------------------------ the refine loop


def _runner(tmp_path, critic, passes, counter):
    """A runner whose agent writes a deliverable and counts each run() call."""

    def build(approver, stack, root):
        class _Agent:
            def run(self, prompt, system=""):
                counter.append(1)
                (root / "deck.txt").write_text(
                    f"draft {len(counter)}", encoding="utf-8"
                )
                return AgentResult(
                    output="done",
                    steps=[
                        AgentStep(
                            tool="write_file",
                            arguments={"path": "deck.txt"},
                            result="wrote deck.txt",
                        )
                    ],
                    stop_reason=StopReason.COMPLETED,
                )

        return _Agent()

    return WebTaskRunner(
        build,
        TaskRepository(tmp_path / "tasks"),
        "m",
        "sys",
        workspace=tmp_path,
        critic=critic,
        refine_passes=passes,
    )


def test_refine_reruns_until_the_critic_is_satisfied(tmp_path):
    calls = {"n": 0}

    def critic(task, content):
        calls["n"] += 1
        return "add detail" if calls["n"] == 1 else ""

    counter: list = []
    _runner(tmp_path, critic, passes=2, counter=counter).start("deck")

    assert _wait(lambda: _done(counter))
    assert len(counter) == 2  # first draft + one revision, then satisfied


def test_refine_is_skipped_when_disabled(tmp_path):
    counter: list = []
    _runner(tmp_path, lambda t, c: "improve", passes=0, counter=counter).start("deck")

    assert _wait(lambda: len(counter) >= 1)
    time.sleep(0.1)
    assert len(counter) == 1  # no refine passes


def test_refine_stops_at_the_pass_limit(tmp_path):
    counter: list = []
    _runner(tmp_path, lambda t, c: "keep going", passes=2, counter=counter).start("d")

    assert _wait(lambda: len(counter) >= 3, timeout=6.0)
    time.sleep(0.1)
    assert len(counter) == 3  # first draft + 2 capped passes


def _done(counter):
    return len(counter) >= 2
