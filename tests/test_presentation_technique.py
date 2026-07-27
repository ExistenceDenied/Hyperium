from __future__ import annotations

from uuid import uuid4

from infrastructure.methodologies.json_methodology_repository import BUILTIN_ROOT
from infrastructure.methodologies.technique_repository import TechniqueRepository
from infrastructure.persistence.task_repository import TaskRepository
from interfaces.web.task_runner import WebApprover, WebTaskRunner, _Run


def test_presentation_technique_ships_with_guidance_and_a_template():
    technique = TechniqueRepository(BUILTIN_ROOT / "techniques").get("presentation")
    assert technique is not None
    assert "recommendation" in technique.guidance.lower()
    assert "Executive summary" in technique.template


def _runner(tmp_path):
    return WebTaskRunner(
        lambda approver, stack, root: None,
        TaskRepository(tmp_path / "tasks"),
        "m",
        "sys",
        workspace=tmp_path,
        approach=lambda tech, meth: f"APPROACH[{tech}]" if tech else "",
        default_technique=lambda p: "presentation" if "deck" in p.lower() else "",
    )


def _run(prompt, technique=""):
    return _Run(
        id=uuid4(), prompt=prompt, approver=WebApprover(), technique=technique
    )


def test_a_deck_task_auto_applies_the_presentation_technique(tmp_path):
    runner = _runner(tmp_path)
    out = runner._prompt(_run("Make a deck about our Q3 results"))
    assert "APPROACH[presentation]" in out


def test_a_plain_task_gets_no_technique(tmp_path):
    runner = _runner(tmp_path)
    assert "APPROACH[" not in runner._prompt(_run("What are our opening hours?"))


def test_an_explicit_technique_is_not_overridden(tmp_path):
    runner = _runner(tmp_path)
    out = runner._prompt(_run("Make a deck", technique="business-case"))
    assert "APPROACH[business-case]" in out  # the task's own choice wins
