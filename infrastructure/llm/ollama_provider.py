from __future__ import annotations

import ollama

from core.interfaces.llm_provider import LLMProvider


class OllamaProvider(LLMProvider):
    """
    LLM provider backed by Ollama.

    A timeout is not optional in practice: without one a stalled model holds
    the engagement open indefinitely, and the retry policy wrapping this
    provider never gets a chance to fire because the call never returns.
    """

    def __init__(
        self,
        model: str = "qwen3:latest",
        timeout_seconds: float = 300.0,
        temperature: float | None = None,
        host: str | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout_seconds
        self._temperature = temperature
        self._client = ollama.Client(host=host, timeout=timeout_seconds)

    def generate(self, prompt: str) -> str:
        options = {}

        if self._temperature is not None:
            options["temperature"] = self._temperature

        response = self._client.chat(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            options=options or None,
        )

        return response["message"]["content"]
