from __future__ import annotations

import pytest

from core.methodologies.technique import Technique
from infrastructure.methodologies.technique_repository import TechniqueRepository
from interfaces.web.server import Download, ReviewApp


def _repo(tmp_path):
    return TechniqueRepository(tmp_path / "techniques")


def test_create_read_update_delete(tmp_path):
    repo = _repo(tmp_path)

    repo.save(
        Technique(
            key="swot",
            name="SWOT",
            description="Strengths, weaknesses, opportunities, threats.",
            guidance="Be specific and evidenced.",
            capabilities=frozenset({"BUSINESS_ANALYSIS"}),
        )
    )
    assert repo.get("swot").name == "SWOT"
    assert "swot" in {t.key for t in repo.list()}

    repo.save(Technique(key="swot", name="SWOT Analysis"))
    assert repo.get("swot").name == "SWOT Analysis"

    repo.delete("swot")
    assert repo.get("swot") is None


def test_save_rejects_unknown_capability(tmp_path):
    repo = _repo(tmp_path)

    with pytest.raises(ValueError):
        repo.save(Technique(key="x", name="X", capabilities=frozenset({"MAGIC"})))


def test_template_upload_download_and_injection(tmp_path):
    repo = _repo(tmp_path)
    repo.save(Technique(key="swot", name="SWOT"))

    assert repo.template_bytes("swot") is None

    repo.save_template("swot", b"# SWOT\n## Strengths\n## Weaknesses\n")

    assert b"Strengths" in repo.template_bytes("swot")
    # The template travels with the technique, so an activity can follow it.
    assert "Strengths" in repo.get("swot").template

    repo.delete_template("swot")
    assert repo.template_bytes("swot") is None


def test_web_crud_and_template_routes(tmp_path):
    repo = _repo(tmp_path)
    app = ReviewApp(service=None, projects=None, techniques=repo)

    # create
    code, redirect = app.post(
        "/techniques",
        {
            "key": ["swot"],
            "name": ["SWOT"],
            "description": ["x"],
            "guidance": ["g"],
            "capabilities": ["BUSINESS_ANALYSIS"],
        },
    )
    assert code == 303 and redirect == "/techniques/swot"
    assert repo.get("swot") is not None

    # it appears in the list
    code, body = app.get("/techniques", {})
    assert code == 200 and "SWOT" in body

    # upload a template (multipart)
    code, _ = app.upload(
        "/techniques/swot/template", {}, [("swot.md", b"# SWOT template")]
    )
    assert code == 303
    assert repo.has_template("swot")

    # download it
    code, download = app.get("/techniques/swot/template", {})
    assert code == 200
    assert isinstance(download, Download)
    assert download.content == b"# SWOT template"

    # delete the technique
    code, redirect = app.post("/techniques/swot/delete", {})
    assert code == 303 and redirect == "/techniques"
    assert repo.get("swot") is None
