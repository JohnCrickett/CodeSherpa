"""Tests for environment configuration loading and validation."""


import pytest

from codesherpa.config import MissingConfigError, load_config


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_loads_all_required_variables(self, tmp_path, monkeypatch):
        """Config loads all required env vars from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ORACLE_DSN=localhost:1521/FREEPDB1\n"
            "ORACLE_USER=user\n"
            "ORACLE_PASSWORD=pass\n"
            "LLM_API_KEY=sk-test\n"
            "LLM_MODEL=gpt-4o\n"
        )
        config = load_config(str(env_file))
        assert config.oracle_dsn == "localhost:1521/FREEPDB1"
        assert config.oracle_user == "user"
        assert config.oracle_password == "pass"
        assert config.llm_api_key == "sk-test"
        assert config.llm_model == "gpt-4o"

    def test_raises_on_missing_required_variable(self, tmp_path):
        """Config raises MissingConfigError when a required var is absent."""
        env_file = tmp_path / ".env"
        env_file.write_text("ORACLE_DSN=localhost:1521/FREEPDB1\n")
        with pytest.raises(MissingConfigError):
            load_config(str(env_file))

    def test_no_credentials_hardcoded(self):
        """Ensure config module does not contain hardcoded credentials."""
        import inspect

        from codesherpa import config

        source = inspect.getsource(config)
        for keyword in ["sk-", "password123", "secret"]:
            assert keyword not in source.lower(), f"Possible hardcoded credential: {keyword}"

    def test_config_has_no_base_url_field(self, tmp_path):
        """Config does not expose a base_url field (Gemini doesn't need one)."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ORACLE_DSN=localhost:1521/FREEPDB1\n"
            "ORACLE_USER=user\n"
            "ORACLE_PASSWORD=pass\n"
            "LLM_API_KEY=test-key\n"
            "LLM_MODEL=gemini-2.5-flash\n"
        )
        config = load_config(str(env_file))
        assert not hasattr(config, "llm_base_url")
