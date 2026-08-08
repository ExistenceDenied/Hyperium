"""
Version comparison.

Immutable versioning was delivered so that revisions could be compared. Until
now nothing consumed it: v1 and v2 sat on disk with no way to see what the
rework actually changed.
"""

from __future__ import annotations

import difflib
import html

from core.execution.deliverable_version import DeliverableVersion


def unified(
    before: DeliverableVersion,
    after: DeliverableVersion,
    context: int = 3,
) -> str:
    """Render a unified diff between two versions as safe HTML."""
    lines = difflib.unified_diff(
        before.content.splitlines(),
        after.content.splitlines(),
        fromfile=before.filename,
        tofile=after.filename,
        lineterm="",
        n=context,
    )

    rows = []

    for line in lines:
        text = html.escape(line, quote=False) or "&nbsp;"

        if line.startswith("+++") or line.startswith("---"):
            css = "meta"
        elif line.startswith("@@"):
            css = "hunk"
        elif line.startswith("+"):
            css = "add"
        elif line.startswith("-"):
            css = "del"
        else:
            css = "same"

        rows.append(f'<div class="diff-line {css}">{text}</div>')

    if not rows:
        return '<p class="muted">No textual differences.</p>'

    return '<div class="diff">' + "".join(rows) + "</div>"


def summary(
    before: DeliverableVersion,
    after: DeliverableVersion,
) -> tuple[int, int]:
    """Return (added, removed) line counts."""
    added = removed = 0

    for line in difflib.unified_diff(
        before.content.splitlines(),
        after.content.splitlines(),
        lineterm="",
    ):
        if line.startswith("+") and not line.startswith("+++"):
            added += 1
        elif line.startswith("-") and not line.startswith("---"):
            removed += 1

    return added, removed
