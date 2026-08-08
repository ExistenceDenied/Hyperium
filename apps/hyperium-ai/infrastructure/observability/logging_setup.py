from __future__ import annotations

import logging
from pathlib import Path

_CONFIGURED = False


def configure_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """
    Configure application logging once per process.

    Writes to stderr and, when a path is given, to a file. Idempotent so that
    importing a module never reconfigures a host application's logging.
    """
    global _CONFIGURED

    if _CONFIGURED:
        return

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        handlers=handlers,
    )

    _CONFIGURED = True
