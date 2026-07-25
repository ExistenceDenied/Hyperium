from __future__ import annotations

from abc import ABC, abstractmethod

from core.execution.activity import Activity
from core.interfaces.llm_provider import LLMProvider


class ActivityExecutor(ABC):
    """
    Produces the content for one activity from its fully-built prompt.

    The engine owns the prompt — persona, upstream work, technique guidance,
    revision feedback. How that prompt becomes content is the strategy this
    abstracts: a plain model completes it in one shot; an agent may use tools
    to gather real information first. The plan, its ordering and its quality
    gates are unaffected either way — only the means of producing content
    changes, so the deterministic-planning guarantee holds.
    """

    @abstractmethod
    def execute(self, prompt: str, activity: Activity) -> str:
        raise NotImplementedError


class LlmActivityExecutor(ActivityExecutor):
    """One completion, no tools — the original engine behaviour."""

    def __init__(self, llm: LLMProvider) -> None:
        self._llm = llm

    def execute(self, prompt: str, activity: Activity) -> str:
        return self._llm.generate(prompt)
