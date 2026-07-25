from __future__ import annotations

from pathlib import Path


def confine(root: Path, raw: str) -> Path | None:
    """
    Resolve ``raw`` under ``root``, or return None if it escapes.

    Escaping covers both ``..`` traversal and symlinks, because ``resolve()``
    follows links before the containment check. A file tool that can wander the
    whole disk is not read-only in any meaningful sense.
    """
    candidate = (root / raw).resolve()

    if candidate == root or root in candidate.parents:
        return candidate

    return None
