from __future__ import annotations

from core.capabilities.capability_catalog import CapabilityCatalog
from core.execution.prompting.capability_prompt_library import (
    known_capabilities,
    prompt_for,
)


def test_every_capability_has_an_authored_md_prompt():
    # The .md files are the single source; each catalogue capability needs one.
    assert set(known_capabilities()) == set(CapabilityCatalog.keys())

    for key in known_capabilities():
        prompt = prompt_for(key)
        assert prompt.persona
        assert len(prompt.guidance) > 150  # real guidance, not a stub


def test_presentation_guidance_is_slide_craft_and_render_ready():
    prompt = prompt_for("PRESENTATION_DESIGN")
    lowered = prompt.guidance.lower()

    assert "slide" in lowered
    assert "speaker note" in lowered
    # It tells the model the exact structure that renders to a real deck.
    assert "##" in prompt.guidance


def test_an_unknown_capability_falls_back_to_a_default():
    prompt = prompt_for("NOT_A_CAPABILITY")

    assert prompt.persona
    assert prompt.guidance
