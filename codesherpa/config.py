"""Environment configuration loading and validation."""

import os
import re
from dataclasses import dataclass

from dotenv import dotenv_values


class MissingConfigError(Exception):
    """Raised when required environment variables are missing."""


REQUIRED_VARS = [
    "ORACLE_DSN",
    "ORACLE_USER",
    "ORACLE_PASSWORD",
    "LLM_API_KEY",
    "LLM_MODEL",
]

_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment."""

    oracle_dsn: str
    oracle_user: str
    oracle_password: str
    llm_api_key: str
    llm_model: str


def _resolve_env_refs(value: str) -> str:
    """Resolve ${VAR} references in a value using the process environment."""
    return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), value)


def load_config(env_path: str = ".env") -> Config:
    """Load and validate configuration from a .env file.

    Values may reference environment variables using ${VAR_NAME} syntax,
    e.g. LLM_API_KEY=${GOOGLE_API_KEY}.

    Args:
        env_path: Path to the .env file.

    Returns:
        A validated Config instance.

    Raises:
        MissingConfigError: If any required variable is missing.
    """
    raw_values = dotenv_values(env_path)
    values = {k: _resolve_env_refs(v) for k, v in raw_values.items() if v is not None}

    missing = [var for var in REQUIRED_VARS if not values.get(var)]
    if missing:
        raise MissingConfigError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    return Config(
        oracle_dsn=values["ORACLE_DSN"],
        oracle_user=values["ORACLE_USER"],
        oracle_password=values["ORACLE_PASSWORD"],
        llm_api_key=values["LLM_API_KEY"],
        llm_model=values["LLM_MODEL"],
    )
