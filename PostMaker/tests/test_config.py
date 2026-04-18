"""配置加载测试"""

import os
from pathlib import Path

from postmaker.core.config import load_config, get_persona_dir


def test_load_config():
    cfg = load_config()
    assert "ai" in cfg
    assert "dataradar" in cfg
    assert "output" in cfg


def test_env_override(monkeypatch):
    monkeypatch.setenv("AI_API_KEY", "test-key-123")
    monkeypatch.setenv("AI_MODEL", "openai/gpt-4")
    cfg = load_config()
    assert cfg["ai"]["api_key"] == "test-key-123"
    assert cfg["ai"]["model"] == "openai/gpt-4"


def test_persona_dir():
    d = get_persona_dir()
    assert d.name == "personas"
    assert d.parent.name == "config"
