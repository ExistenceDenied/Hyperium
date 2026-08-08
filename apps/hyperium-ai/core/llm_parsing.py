from __future__ import annotations

import json
import re

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def extract_json_object(response: str | None) -> dict | None:
    """
    Pull a single JSON object out of a local model's reply.

    Reasoning models wrap their answer in <think>…</think> and often add prose
    around the JSON. This strips the reasoning (including the common case of a
    lone closing tag) and greedily matches the outer object, returning the
    parsed dict, or None when there is nothing usable. Every JSON-mode caller —
    triage, the critic, the reviewers, the analysis parser — shares this so the
    fragile local-LLM extraction lives in one place.
    """
    text = _THINK.sub("", response or "").strip()
    close = text.lower().rfind("</think>")
    if close != -1:
        text = text[close + len("</think>"):]

    match = _OBJECT.search(text)
    if match is None:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None
