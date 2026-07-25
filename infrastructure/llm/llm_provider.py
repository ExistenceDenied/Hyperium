from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Abstract base class for all LLM providers.
    """

    @abstractmethod
    def ask(self, prompt: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def ask_json(self, prompt: str) -> dict:
        raise NotImplementedError