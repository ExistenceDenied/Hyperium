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


def _env_bool(name: str, default: bool) -> bool:
    return _env(name, "1" if default else "0").strip().lower() in (
        "1", "true", "yes", "on"
    )


@dataclass(frozen=True)
class Settings:
    """
    Runtime configuration, overridable through HYPERIUM_* environment
    variables so that behaviour is configured rather than hardcoded.
    """

    model: str = "qwen3:latest"
    # The reviewer can use a sharper model than the worker: review runs less
    # often, and it sets the quality bar. Empty means "same as `model`".
    review_model: str = ""
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
    # Whether a direct task's agent is also handed every connected tool. Off by
    # default: a local model chooses badly among hundreds of tools, and it made
    # deliverable tasks fail ("none of the functions apply"). The email worker
    # reaches Outlook directly, so this does not affect it.
    task_connectors: bool = False
    # Draft -> critique -> revise passes spent improving a produced deliverable.
    # 0 (default) is fastest; 1-2 trades time for noticeably better quality.
    refine_passes: int = 0

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            model=_env("MODEL", cls.model),
            review_model=_env("REVIEW_MODEL", cls.review_model),
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
            task_connectors=_env_bool("TASK_CONNECTORS", cls.task_connectors),
            refine_passes=_env_int("REFINE_PASSES", cls.refine_passes),
        )
