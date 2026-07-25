from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(f"HYPERIUM_{name}", default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """
    Runtime configuration, overridable through HYPERIUM_* environment
    variables so that behaviour is configured rather than hardcoded.
    """

    model: str = "qwen3:latest"
    temperature: float = 0.2
    workspace: Path = Path("workspace")
    state_directory: Path = Path("workspace/.hyperium")
    llm_attempts: int = 3
    llm_backoff_seconds: float = 2.0
    llm_timeout_seconds: float = 300.0
    log_level: str = "INFO"
    log_file: Path = Path("logs/hyperium.log")
    methodology_directory: Path | None = None
    default_methodology: str = "business-analysis"

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            model=_env("MODEL", cls.model),
            temperature=_env_float("TEMPERATURE", cls.temperature),
            workspace=Path(_env("WORKSPACE", str(cls.workspace))),
            state_directory=Path(_env("STATE_DIR", str(cls.state_directory))),
            llm_attempts=_env_int("LLM_ATTEMPTS", cls.llm_attempts),
            llm_backoff_seconds=_env_float(
                "LLM_BACKOFF", cls.llm_backoff_seconds
            ),
            llm_timeout_seconds=_env_float(
                "LLM_TIMEOUT", cls.llm_timeout_seconds
            ),
            log_level=_env("LOG_LEVEL", cls.log_level),
            log_file=Path(_env("LOG_FILE", str(cls.log_file))),
            methodology_directory=(
                Path(_env("METHODOLOGIES", "")) if _env("METHODOLOGIES", "") else None
            ),
            default_methodology=_env(
                "DEFAULT_METHODOLOGY", cls.default_methodology
            ),
        )
