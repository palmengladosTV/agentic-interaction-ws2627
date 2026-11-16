"""Configuration from the environment, with .env as a fallback."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED = ("OPENAI_BASE_URL", "MODEL", "OPENAI_API_KEY", "DATA_BASE_URL")
# Upper bound on steps (model calls) per run, optionally overridden by MAX_STEPS. Without it, a
# model that keeps calling tools would loop forever, and every step resends the whole history.
DEFAULT_MAX_STEPS = 10


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    base_url: str
    model: str
    api_key: str
    data_base_url: str
    max_steps: int = DEFAULT_MAX_STEPS


def load_config() -> Config:
    # override=False: variables already set in the environment win over .env.
    load_dotenv(REPO_ROOT / ".env", override=False)
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise ConfigError(
            f"missing configuration: {', '.join(missing)} (set them in the environment or in .env)"
        )
    return Config(
        base_url=os.environ["OPENAI_BASE_URL"],
        model=os.environ["MODEL"],
        api_key=os.environ["OPENAI_API_KEY"],
        data_base_url=os.environ["DATA_BASE_URL"].rstrip("/"),
        max_steps=_max_steps(),
    )


def _max_steps() -> int:
    raw = os.environ.get("MAX_STEPS", "").strip()
    if not raw:
        return DEFAULT_MAX_STEPS
    if not raw.isdigit() or int(raw) < 1:
        raise ConfigError(f"MAX_STEPS must be a positive whole number, got {raw!r}")
    return int(raw)
