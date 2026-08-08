from __future__ import annotations

from application.project.project_builder import ProjectBuilder
from core.execution.prompting.activity_prompt_builder import ActivityPromptBuilder
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from infrastructure.templates import TemplateLibrary
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


class FakeTemplates:
    def get(self, key):
        return "## FIXED HEADING\nfill me" if key == "requirements" else None


def _deliverable_and_mission():
    service = ProjectBuilder.build(
        ScriptedLLM(), InMemoryArtifactStore(), methodologies=FakeMethodologies()
    )
    project = service.start(build_mission(), resources=[build_consultant()])
    deliverable = project.deliverable("requirements")
    return deliverable, deliverable.activities[0], project.mission


def test_library_loads_the_shipped_slide_template():
    template = TemplateLibrary().get("slide-outline")

    assert template is not None
    assert "Speaker note" in template  # render-ready structure is present


def test_library_returns_none_for_an_unknown_deliverable(tmp_path):
    assert TemplateLibrary(tmp_path).get("does-not-exist") is None


def test_prompt_embeds_the_template_when_one_exists():
    deliverable, activity, mission = _deliverable_and_mission()

    prompt = ActivityPromptBuilder(templates=FakeTemplates()).build(
        activity, deliverable, mission
    )

    assert "FIXED HEADING" in prompt
    assert "must follow this exactly" in prompt


def test_prompt_omits_the_template_section_without_a_library():
    deliverable, activity, mission = _deliverable_and_mission()

    prompt = ActivityPromptBuilder().build(activity, deliverable, mission)

    assert "must follow this exactly" not in prompt
