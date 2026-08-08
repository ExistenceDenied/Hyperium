from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CapabilityPrompt:
    """
    The consulting persona and working instructions for one capability.

    This is where professional expertise lives. It replaces the per-agent
    system prompts of the retired agent model: expertise is now bound to a
    capability, so a human or an external service could satisfy the same
    activity without the prompt changing.

    The text is authored as one Markdown file per capability in the
    `capabilities/` folder beside this module — data, not code — so the
    instructions that decide output quality can be edited without touching
    Python. The file's front-matter carries the persona; its body is the
    guidance.
    """

    persona: str
    guidance: str


_DIRECTORY = Path(__file__).parent / "capabilities"
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
_PERSONA = re.compile(r"(?mi)^persona:\s*(.+)$")

_DEFAULT = CapabilityPrompt(
    persona="a senior management consultant",
    guidance=(
        "Produce a clear, well-structured professional document. "
        "Prefer specifics over generalities."
    ),
)


def _parse(text: str) -> CapabilityPrompt:
    match = _FRONT_MATTER.match(text)

    if not match:
        return CapabilityPrompt(_DEFAULT.persona, text.strip())

    meta, body = match.group(1), match.group(2)
    persona = _PERSONA.search(meta)

    return CapabilityPrompt(
        persona=persona.group(1).strip() if persona else _DEFAULT.persona,
        guidance=body.strip(),
    )


def _load() -> dict[str, CapabilityPrompt]:
    library: dict[str, CapabilityPrompt] = {}

    if _DIRECTORY.is_dir():
        for path in sorted(_DIRECTORY.glob("*.md")):
            library[path.stem.upper()] = _parse(path.read_text(encoding="utf-8"))

    return library


_LIBRARY = _load()


def prompt_for(capability_key: str) -> CapabilityPrompt:
    return _LIBRARY.get(capability_key.strip().upper(), _DEFAULT)


def known_capabilities() -> tuple[str, ...]:
    return tuple(_LIBRARY)
