"""配置加载"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml

_PROJECT_ROOT = Path(__file__).parent.parent.parent


def load_config(config_path: str | None = None) -> Dict[str, Any]:
    if config_path is None:
        config_path = str(_PROJECT_ROOT / "config" / "config.yaml")
    path = Path(config_path)
    if not path.exists():
        return _defaults()

    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    _apply_env(cfg)
    return cfg


def _apply_env(cfg: Dict[str, Any]) -> None:
    dataradar = cfg.setdefault("dataradar", {})
    if os.environ.get("DATARADAR_API_BASE"):
        dataradar["api_base"] = os.environ["DATARADAR_API_BASE"]
    if os.environ.get("DATARADAR_TIMEOUT"):
        try:
            dataradar["timeout"] = int(os.environ["DATARADAR_TIMEOUT"])
        except ValueError:
            pass

    ai = cfg.setdefault("ai", {})
    if not ai.get("api_key"):
        ai["api_key"] = os.environ.get("AI_API_KEY", "")
    if not ai.get("api_base"):
        ai["api_base"] = os.environ.get("AI_API_BASE", "")
    if not ai.get("model"):
        ai["model"] = os.environ.get("AI_MODEL", "")

    db = cfg.setdefault("database", {})
    if not db.get("postgres_dsn"):
        db["postgres_dsn"] = os.environ.get("POSTGRES_DSN", "")


def _defaults() -> Dict[str, Any]:
    return {
        "app": {"timezone": "Asia/Shanghai"},
        "dataradar": {"api_base": "http://localhost:8000", "timeout": 15},
        "ai": {
            "model": os.environ.get("AI_MODEL", ""),
            "api_key": os.environ.get("AI_API_KEY", ""),
            "api_base": os.environ.get("AI_API_BASE", ""),
            "timeout": 120,
            "temperature": 0.7,
            "max_tokens": 8000,
            "refine_enabled": False,
            "models": {"high": "", "medium": ""},
        },
        "database": {"postgres_dsn": os.environ.get("POSTGRES_DSN", "")},
        "output": {"base_dir": "output", "formats": ["markdown", "html"]},
    }


def get_persona_dir(cfg: Dict[str, Any] | None = None) -> Path:
    return _PROJECT_ROOT / "config" / "personas"
