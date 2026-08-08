from __future__ import annotations

import logging
import time

from core.interfaces.llm_provider import LLMProvider

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """
    Raised when a provider still fails after every retry.
    """


class ResilientProvider(LLMProvider):
    """
    Wraps a provider with bounded retries and exponential backoff.

    A consulting engagement runs long enough that a transient provider failure
    is a certainty rather than an edge case. Without this, one blip discards
    every activity completed so far.
    """

    def __init__(
        self,
        inner: LLMProvider,
        attempts: int = 3,
        backoff_seconds: float = 2.0,
        sleep=time.sleep,
    ) -> None:
        if attempts < 1:
            raise ValueError("attempts must be at least 1.")

        self._inner = inner
        self._attempts = attempts
        self._backoff = backoff_seconds
        self._sleep = sleep

    def generate(self, prompt: str) -> str:
        last_error: Exception | None = None

        for attempt in range(1, self._attempts + 1):
            try:
                response = self._inner.generate(prompt)
            except Exception as error:  # provider SDKs raise freely
                last_error = error
                logger.warning(
                    "LLM attempt %s/%s failed: %s",
                    attempt,
                    self._attempts,
                    error,
                )
            else:
                if response and response.strip():
                    return response

                last_error = LLMUnavailableError("Provider returned no content.")
                logger.warning(
                    "LLM attempt %s/%s returned empty content.",
                    attempt,
                    self._attempts,
                )

            if attempt < self._attempts:
                self._sleep(self._backoff * (2 ** (attempt - 1)))

        raise LLMUnavailableError(
            f"Provider failed after {self._attempts} attempts: {last_error}"
        ) from last_error
