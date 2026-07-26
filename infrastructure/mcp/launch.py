from __future__ import annotations

import os
import shutil
from collections.abc import Sequence


def resolve_argv(command: str, args: Sequence[str] = ()) -> list[str]:
    """
    Build an argv that launches on Windows as well as POSIX.

    A bare name like ``npx`` is really ``npx.cmd`` on Windows, which
    CreateProcess cannot run directly — so resolve it on PATH and route a
    ``.cmd``/``.bat`` through ``cmd /c``. Without this, every npx-based
    connector (and its device sign-in) fails with "the system cannot find the
    file specified". On POSIX this just uses the resolved path.
    """
    resolved = shutil.which(command) or command
    if os.name == "nt" and resolved.lower().endswith((".cmd", ".bat")):
        return ["cmd", "/c", resolved, *args]
    return [resolved, *args]
