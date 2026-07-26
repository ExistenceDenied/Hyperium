from __future__ import annotations

from application.email.email_triage import EmailTriage
from core.email.email_message import EmailMessage
from core.interfaces.llm_provider import LLMProvider


class _LLM(LLMProvider):
    def __init__(self, response):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return self.response


def _msg():
    return EmailMessage(
        id="m1", sender="c@acme.com", subject="Quote?", body="How much?"
    )


def test_parses_a_reply_decision_with_tasks():
    llm = _LLM(
        '{"category": "reply", "priority": "high", "confidence": 0.9,'
        ' "summary": "Wants a quote", "reason": "direct question",'
        ' "tasks": ["Prepare a quote"]}'
    )

    decision = EmailTriage(llm).classify(_msg(), context="We sell widgets.")

    assert decision.category == "reply"
    assert decision.should_draft is True
    assert decision.priority == "high"
    assert decision.tasks == ["Prepare a quote"]
    assert "We sell widgets." in llm.prompts[0]  # memory reaches the classifier


def test_strips_think_blocks_before_parsing():
    llm = _LLM('<think>hmm</think>{"category": "skip", "tasks": []}')

    assert EmailTriage(llm).classify(_msg()).category == "skip"


def test_unknown_category_becomes_escalate():
    llm = _LLM('{"category": "banana", "tasks": []}')

    decision = EmailTriage(llm).classify(_msg())

    assert decision.category == "escalate"
    assert decision.needs_attention is True


def test_unparseable_response_escalates_rather_than_guessing():
    decision = EmailTriage(_LLM("not json at all")).classify(_msg())

    assert decision.category == "escalate"


def test_a_failing_model_call_escalates():
    class _Boom(LLMProvider):
        def generate(self, prompt):
            raise RuntimeError("model down")

    assert EmailTriage(_Boom()).classify(_msg()).category == "escalate"


def test_task_list_is_capped():
    llm = _LLM('{"category": "fyi", "tasks": ["a", "b", "c", "d", "e"]}')

    decision = EmailTriage(llm, task_limit=2).classify(_msg())

    assert decision.tasks == ["a", "b"]
