"""Tests for configuration loading and environment variable overrides."""

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestConfigLoader:
    def test_load_config_returns_dict(self):
        from dataradar.core.loader import load_config

        config = load_config()
        assert isinstance(config, dict)

    def test_config_has_required_keys(self):
        from dataradar.core.loader import load_config

        config = load_config()
        assert "TIMEZONE" in config
        assert "AI" in config
        assert "STORAGE" in config

    def test_ai_config_structure(self):
        from dataradar.core.loader import load_config

        config = load_config()
        ai = config.get("AI", {})
        assert "MODEL" in ai
        assert "API_KEY" in ai
        assert "TIMEOUT" in ai

    def test_env_var_override_ai_key(self, monkeypatch):
        monkeypatch.setenv("AI_API_KEY", "test-env-key-123")
        from dataradar.core.loader import load_config

        config = load_config()
        assert config["AI"]["API_KEY"] == "test-env-key-123"

    def test_env_var_override_ai_model(self, monkeypatch):
        monkeypatch.setenv("AI_MODEL", "deepseek/deepseek-chat")
        from dataradar.core.loader import load_config

        config = load_config()
        assert config["AI"]["MODEL"] == "deepseek/deepseek-chat"

    def test_env_var_override_postgres_dsn(self, monkeypatch):
        monkeypatch.setenv("POSTGRES_DSN", "postgresql://test:test@localhost/test")
        from dataradar.core.loader import load_config

        config = load_config()
        kb = config.get("KNOWLEDGE_BASE", {})
        assert kb.get("POSTGRES_DSN") == "postgresql://test:test@localhost/test"

    def test_default_timezone(self):
        from dataradar.core.loader import load_config

        config = load_config()
        assert config.get("TIMEZONE") is not None

    def test_no_plaintext_key_in_default_config(self):
        from dataradar.core.loader import load_config

        config = load_config()
        api_key = config.get("AI", {}).get("API_KEY", "")
        assert not api_key.startswith("sk-"), \
            "API key should not be hardcoded in config"
