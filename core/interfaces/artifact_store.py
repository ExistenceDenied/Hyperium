from __future__ import annotations

from abc import ABC, abstractmethod


class ArtifactStore(ABC):
    """
    Interface for storing deliverable content.

    The execution layer depends on this abstraction rather than on the
    filesystem, so where artifacts live stays an infrastructure decision.
    """

    @abstractmethod
    def save(self, filename: str, content: str) -> str:
        """
        Persist the content and return a human-readable location.
        """
        raise NotImplementedError

    @abstractmethod
    def read(self, filename: str) -> str:
        """
        Return previously stored content.
        """
        raise NotImplementedError
