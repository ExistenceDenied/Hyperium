from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """
    Interface for Large Language Model providers.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Generate a response from the supplied prompt.
        """
        raise NotImplementedError