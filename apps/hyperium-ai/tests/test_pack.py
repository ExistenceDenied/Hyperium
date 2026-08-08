from __future__ import annotations

from application.project.project_builder import ProjectBuilder
from infrastructure.artifacts.file_artifact_store import InMemoryArtifactStore
from interfaces.pack import build_html_pack
from tests.fixtures import (
    FakeMethodologies,
    ScriptedLLM,
    build_consultant,
    build_mission,
)


def _project():
    service = ProjectBuilder.build(
        ScriptedLLM(), InMemoryArtifactStore(), methodologies=FakeMethodologies()
    )
    return service.start(build_mission(), resources=[build_consultant()])


def test_pack_is_a_self_contained_document():
    html = build_html_pack(_project())

    assert html.startswith("<!doctype html>")
    assert "<style>" in html  # styles inlined, nothing external
    assert "http://" not in html and "https://" not in html


def test_pack_includes_the_mission_and_a_delivered_section():
    project = _project()

    html = build_html_pack(project)

    assert project.mission.title in html
    # The Discovery deliverable and its generated content are both present.
    assert "Training Requirements" in html
    assert "Learning needs" in html


def test_pack_has_a_table_of_contents_entry_per_deliverable():
    project = _project()

    html = build_html_pack(project)

    delivered = [d for d in project.deliverables if d.latest_version() is not None]
    assert delivered
    for deliverable in delivered:
        assert f"#{deliverable.key}" in html
