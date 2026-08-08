from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path, data) -> None:
    """
    Write JSON so a concurrent reader never sees a half-written file.

    The stores are written from background threads (the queue worker, the
    scheduler, the inbox worker) and read from web requests at the same time. A
    bare write_text can be read mid-flush — a truncated file that fails to parse
    and, at worst, corrupts state. Writing to a temp file in the same directory
    and os.replace-ing it in makes the swap atomic: a reader gets either the old
    file or the new one, never a partial one.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
        os.replace(tmp, target)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
