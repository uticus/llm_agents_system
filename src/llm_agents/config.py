"""Typed runtime configuration.

Loads settings from environment variables (prefix ``LLM_AGENTS_``) and an optional
YAML file under ``configs/``. Kept dependency-light: only the standard library is used
so importing the package never requires third-party settings libraries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ENV_PREFIX = "LLM_AGENTS_"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "default.yaml"


@dataclass(frozen=True)
class Settings:
    """Resolved runtime settings."""

    environment: str = "dev"
    log_level: str = "INFO"
    # Reproducibility: a fixed seed for any non-LLM randomness (sampling, shuffling).
    seed: int = 0
    # Tracing/observability toggles.
    tracing_enabled: bool = True
    metrics_enabled: bool = True
    extra: dict[str, str] = field(default_factory=dict)


def _from_env() -> dict[str, str]:
    return {
        key[len(ENV_PREFIX) :].lower(): value
        for key, value in os.environ.items()
        if key.startswith(ENV_PREFIX)
    }


def load_settings() -> Settings:
    """Build Settings from environment variables, falling back to defaults.

    YAML loading is intentionally deferred: when a config loader is added, parse
    DEFAULT_CONFIG_PATH here and merge it under the environment overrides.
    """
    env = _from_env()
    return Settings(
        environment=env.get("environment", "dev"),
        log_level=env.get("log_level", "INFO"),
        seed=int(env.get("seed", "0")),
        tracing_enabled=env.get("tracing_enabled", "true").lower() == "true",
        metrics_enabled=env.get("metrics_enabled", "true").lower() == "true",
    )
