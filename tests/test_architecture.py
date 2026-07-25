"""
Architecture fitness functions.

The documentation asserts around thirty invariants — "dependencies point
inward", "business contexts must never depend on AI providers", "quality gate
decisions belong to Hyperium". Until this file existed, none of them were
checked by anything, and the code drifted from the docs without anyone
noticing.

These tests turn prose invariants into build failures. They are deliberately
crude: they read import statements, not semantics. That is enough to catch the
drift that actually happens.
"""

from __future__ import annotations

import ast
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent

LAYERS = ("core", "application", "infrastructure", "interfaces")

# Dependencies point inward. A layer may import itself and anything to its
# right in this mapping.
ALLOWED: dict[str, set[str]] = {
    "core": {"core"},
    "application": {"application", "core"},
    "infrastructure": {"infrastructure", "core"},
    "interfaces": {"interfaces", "application", "infrastructure", "core", "config"},
}


def source_files(*roots: str):
    for root in roots:
        for path in (ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def imports_of(path: pathlib.Path) -> set[str]:
    """Top-level package names imported by a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])

    return found


def module_name(path: pathlib.Path) -> str:
    relative = path.relative_to(ROOT).with_suffix("")
    parts = [part for part in relative.parts if part != "__init__"]

    return ".".join(parts)


# ----------------------------------------------------------------- layering


def test_dependencies_point_inward():
    """09-extensibility.md: 'Dependencies should always point inward.'"""
    violations = []

    for layer, allowed in ALLOWED.items():
        for path in source_files(layer):
            for imported in imports_of(path) & set(LAYERS):
                if imported not in allowed:
                    violations.append(
                        f"{module_name(path)} imports '{imported}' "
                        f"(a {layer} module may only import {sorted(allowed)})"
                    )

    assert not violations, "Layering violations:\n  " + "\n  ".join(violations)


def test_the_domain_never_depends_on_an_ai_provider():
    """
    ADR-002: 'Business contexts must never depend directly on AI providers.'
    """
    banned = {"ollama", "openai", "anthropic", "httpx", "requests"}
    violations = []

    for path in source_files("core", "application"):
        for imported in imports_of(path) & banned:
            violations.append(f"{module_name(path)} imports '{imported}'")

    assert not violations, "Provider leak:\n  " + "\n  ".join(violations)


def test_governance_never_consults_a_model():
    """
    05-agents.md reserves quality-gate decisions for Hyperium itself. A gate
    that asked a model whether it had passed would not be a gate.
    """
    violations = []

    for path in source_files("core/methodologies", "core/planning"):
        text = path.read_text(encoding="utf-8")

        if "LLMProvider" in text or "llm" in imports_of(path):
            violations.append(module_name(path))

    assert not violations, (
        "Model reached governance code: " + ", ".join(violations)
    )


# ------------------------------------------------------------------ cycles


def package_of(path: pathlib.Path) -> str:
    relative = path.relative_to(ROOT)

    if len(relative.parts) > 1:
        return ".".join(relative.parts[:2])

    return relative.parts[0]


def test_no_circular_package_dependencies():
    """
    A cycle between two packages means neither can be understood, tested or
    replaced on its own.
    """
    graph: dict[str, set[str]] = defaultdict(set)

    for path in source_files(*LAYERS):
        here = package_of(path)

        for node in ast.walk(
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        ):
            if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                parts = node.module.split(".")

                if parts[0] in LAYERS and len(parts) > 1:
                    there = ".".join(parts[:2])

                    if there != here:
                        graph[here].add(there)

    cycles = {
        tuple(sorted((a, b)))
        for a, targets in graph.items()
        for b in targets
        if a in graph.get(b, set())
    }

    assert not cycles, "Circular package dependencies:\n  " + "\n  ".join(
        f"{a} <-> {b}" for a, b in sorted(cycles)
    )


# ------------------------------------------------------------- consistency


def test_the_two_capability_registries_agree():
    """
    A capability with no prompt strategy silently degrades to a generic
    persona. Nothing else notices, so this does.
    """
    from core.capabilities.capability_catalog import CapabilityCatalog
    from core.execution.prompting.capability_prompt_library import (
        known_capabilities,
    )

    catalogue = set(CapabilityCatalog.keys())
    prompts = set(known_capabilities())

    assert catalogue == prompts, (
        f"Capability registries disagree. "
        f"In the catalogue but with no prompt: {sorted(catalogue - prompts)}. "
        f"Has a prompt but is not a capability: {sorted(prompts - catalogue)}."
    )
