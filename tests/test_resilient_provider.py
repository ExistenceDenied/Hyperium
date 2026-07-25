import pytest

from core.interfaces.llm_provider import LLMProvider
from infrastructure.llm.resilient_provider import (
    LLMUnavailableError,
    ResilientProvider,
)


class FlakyProvider(LLMProvider):
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls = 0

    def generate(self, prompt: str) -> str:
        self.calls += 1
        outcome = self.responses.pop(0)

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


def build(responses, attempts=3):
    inner = FlakyProvider(responses)
    slept: list[float] = []

    provider = ResilientProvider(
        inner,
        attempts=attempts,
        backoff_seconds=1.0,
        sleep=slept.append,
    )

    return provider, inner, slept


def test_returns_the_first_successful_response():
    provider, inner, slept = build(["content"])

    assert provider.generate("prompt") == "content"
    assert inner.calls == 1
    assert slept == []


def test_retries_after_a_transient_failure():
    provider, inner, _ = build([ConnectionError("boom"), "content"])

    assert provider.generate("prompt") == "content"
    assert inner.calls == 2


def test_retries_when_the_provider_returns_empty_content():
    provider, inner, _ = build(["   ", "content"])

    assert provider.generate("prompt") == "content"
    assert inner.calls == 2


def test_backoff_is_exponential():
    provider, _, slept = build(
        [ConnectionError("a"), ConnectionError("b"), "content"]
    )

    provider.generate("prompt")

    assert slept == [1.0, 2.0]


def test_does_not_sleep_after_the_final_attempt():
    provider, _, slept = build([ConnectionError("a"), ConnectionError("b")], attempts=2)

    with pytest.raises(LLMUnavailableError):
        provider.generate("prompt")

    assert slept == [1.0]


def test_raises_after_exhausting_attempts():
    provider, inner, _ = build(
        [ConnectionError("a"), ConnectionError("b"), ConnectionError("c")]
    )

    with pytest.raises(LLMUnavailableError, match="after 3 attempts"):
        provider.generate("prompt")

    assert inner.calls == 3


def test_rejects_a_nonsensical_attempt_count():
    with pytest.raises(ValueError, match="at least 1"):
        ResilientProvider(FlakyProvider([]), attempts=0)
