from __future__ import annotations

from core.capabilities.capability_catalog import CapabilityCatalog
from infrastructure.llm.ollama_provider import OllamaProvider
from infrastructure.methodologies.json_methodology_repository import (
    JsonMethodologyRepository,
)
from infrastructure.templates import TemplateLibrary


def test_copywriting_is_a_registered_capability():
    assert "COPYWRITING" in CapabilityCatalog.keys()


def test_smb_methodologies_load_and_validate():
    repository = JsonMethodologyRepository()

    for key in ("customer-proposal", "marketing-pack"):
        methodology = repository.get(key)
        methodology.validate()  # references COPYWRITING, which must exist

    keys = {item.key for item in repository.all()}
    assert {"customer-proposal", "marketing-pack"} <= keys


def test_proposal_is_a_word_document_written_by_the_copywriter():
    proposal = JsonMethodologyRepository().get("customer-proposal")
    deliverable = {item.key: item for item in proposal.deliverables}["proposal"]

    assert deliverable.format == "docx"
    capabilities = {
        capability
        for activity in deliverable.activities
        for capability in activity.capabilities
    }
    assert "COPYWRITING" in capabilities


def test_smb_deliverables_have_templates():
    library = TemplateLibrary()

    assert library.get("proposal") is not None
    assert library.get("campaign-brief") is not None
    assert library.get("social-posts") is not None


def test_reviewer_json_mode_configures_the_provider():
    provider = OllamaProvider(response_format="json", think=False)

    assert provider._format == "json"
    assert provider._think is False
