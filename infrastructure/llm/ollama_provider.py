from __future__ import annotations

import ollama

from core.interfaces.llm_provider import LLMProvider


class OllamaProvider(LLMProvider):
    """
    LLM provider backed by Ollama.
    """

    def __init__(self, model: str = "qwen3:latest") -> None:
        self._model = model

    def generate(self, prompt: str) -> str:
        response = ollama.chat(
            model=self._model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        )

        return response["message"]["content"]