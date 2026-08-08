from __future__ import annotations

import re

_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_CLOSE = "</think>"


def strip_thinking(text: str | None) -> str:
    """
    Remove a reasoning model's chain-of-thought from its answer.

    Some models (qwen3, and especially the 30b MoE) emit `<think>…</think>`
    reasoning in the content even when thinking is asked to be off. Left in, it
    leaks into email replies and deliverables. This drops any complete think
    block, and — for the common case where the opening tag is missing but a
    closing one remains — keeps only what follows the last `</think>`.
    """
    if not text:
        return text or ""

    cleaned = _BLOCK.sub("", text)
    lowered = cleaned.lower()
    index = lowered.rfind(_CLOSE)
    if index != -1:
        cleaned = cleaned[index + len(_CLOSE):]
    return cleaned.strip()
