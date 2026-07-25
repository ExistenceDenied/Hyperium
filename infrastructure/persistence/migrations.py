"""
Schema migrations for saved engagements.

The schema has changed four times, and each change orphaned every engagement
saved before it. That was tolerable while nothing stored work anyone cared
about; it stops being tolerable the moment someone does.

A migration is a pure function from one schema version to the next. They are
chained, so a version 1 file is upgraded one hop at a time rather than by a
single function that has to know every past shape.

Two rules:

- A migration never guesses at governance. Where an older file genuinely does
  not contain something the new schema needs — a quality gate that did not
  exist in that version — the field is left empty and the loss is logged. It
  is not invented.
- A file from the future is refused. Downgrading would discard data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import uuid4

logger = logging.getLogger(__name__)


class SchemaError(ValueError):
    """
    Raised when a saved engagement cannot be brought to the current schema.
    """


def _epoch() -> str:
    return datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat()


def _v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Version 2 gave the mission its own identity and backlog lifecycle.

    A version 1 mission existed only inside a project, so it is reconstructed
    as an already-launched backlog entry pointing back at that project.
    """
    mission = payload.get("mission") or {}

    mission.setdefault("id", str(uuid4()))
    mission.setdefault("status", "LAUNCHED")
    mission.setdefault("priority", "MEDIUM")
    mission.setdefault("created_at", _epoch())
    mission.setdefault("updated_at", _epoch())
    mission.setdefault("project_id", payload.get("id"))
    mission.setdefault("methodology", None)

    # Version 1 constraints carried only a description.
    for constraint in mission.get("constraints", []):
        constraint.setdefault("type", "OTHER")
        constraint.setdefault("mandatory", True)

    payload["mission"] = mission

    return payload


def _v2_to_v3(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Version 3 introduced methodologies: deliverables gained a stage and a
    section outline, activities gained a technique.

    A version 2 engagement was planned by a model rather than a methodology,
    so it has no stage to belong to. That is recorded as absent, not faked.
    """
    analysis = payload.get("analysis") or {}

    for deliverable in analysis.get("deliverables", []):
        deliverable.setdefault("stage", None)
        deliverable.setdefault("sections", [])

        for activity in deliverable.get("activities", []):
            activity.setdefault("technique", None)

    plan = payload.get("execution_plan")

    if plan is not None:
        plan.setdefault("methodology", None)

    return payload


def _v3_to_v4(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Version 4 moved the work onto the plan, where it belongs, and gave the
    plan its own stages so an engagement keeps the governance it was planned
    with.

    A version 3 file stored only the methodology *key*; the gates lived in the
    methodology and were resolved at read time. Those gates cannot be
    recovered from the file, and reconstructing them from whatever the
    registry holds today would apply rules the engagement was never planned
    under. They are therefore left absent and the loss is reported.
    """
    analysis = payload.get("analysis") or {}
    deliverables = analysis.pop("deliverables", [])
    payload["analysis"] = analysis or None

    plan = payload.get("execution_plan")

    if plan is None:
        return payload

    plan["deliverables"] = deliverables
    plan["methodology_key"] = plan.pop("methodology", None)
    plan.setdefault("stages", [])
    plan.pop("deliverable_order", None)

    if plan["methodology_key"]:
        logger.warning(
            "Engagement %s was planned under methodology '%s' before quality "
            "gates were stored with the plan. It will resume without stage "
            "gates; re-plan it if the gates matter.",
            payload.get("id"),
            plan["methodology_key"],
        )

    return payload


_MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _v1_to_v2,
    2: _v2_to_v3,
    3: _v3_to_v4,
}


def upgrade(payload: dict[str, Any], target: int) -> dict[str, Any]:
    """
    Bring a saved engagement up to `target`, one version at a time.
    """
    version = payload.get("schema_version")

    if not isinstance(version, int):
        raise SchemaError(
            f"Saved engagement has no usable schema version "
            f"({version!r}); it cannot be upgraded safely."
        )

    if version > target:
        raise SchemaError(
            f"Saved engagement uses schema version {version}, which is newer "
            f"than this build understands ({target}). Upgrade Hyperium rather "
            f"than downgrading the file."
        )

    while version < target:
        migration = _MIGRATIONS.get(version)

        if migration is None:
            raise SchemaError(
                f"No migration from schema version {version} to "
                f"{version + 1}."
            )

        logger.info("Upgrading engagement schema %s -> %s.", version, version + 1)

        payload = migration(payload)
        version += 1
        payload["schema_version"] = version

    return payload
