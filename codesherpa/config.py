"""Environment configuration loading and validation."""

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


@dataclass(frozen=True)
class Config:
    """Application configuration loaded from environment."""

    oracle_dsn: str
    oracle_user: str
    oracle_password: str
    llm_api_key: str
    llm_model: str


def load_config(env_path: str = ".env") -> Config:
    """Load and validate configuration from a .env file.

    Args:
        env_path: Path to the .env file.

    Returns:
        A validated Config instance.

    Raises:
        MissingConfigError: If any required variable is missing.
    """
    values = dotenv_values(env_path)

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
