"""Request-scoped workspace paths for hosted, multi-user local mode."""

from __future__ import annotations

import os
import re
import hashlib
import hmac
from contextvars import ContextVar
from pathlib import Path

import yaml

_WORKSPACE_ID = ContextVar("dataradar_workspace_id", default="default")
_VALID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,95}$")


def set_workspace_id(value: str):
    value = (value or "default").strip()
    if value == "default":
        return _WORKSPACE_ID.set("default")
    if not _VALID.fullmatch(value):
        raise ValueError("workspace id 无效")
    return _WORKSPACE_ID.set(value)


def reset_workspace(token) -> None:
    _WORKSPACE_ID.reset(token)


def workspace_id() -> str:
    return _WORKSPACE_ID.get()


def workspace_root() -> Path:
    base = Path(os.getenv("DATARADAR_WORKSPACES_DIR", "output/workspaces"))
    return base / workspace_id()


def workspace_config_path() -> Path:
    return workspace_root() / "config.yaml"


def ensure_workspace_config() -> Path:
    """Create an isolated first-run config without copying shared sources.

    A hosted workspace must never fall back to the repository-level config: that
    would expose another user's RSS definitions and could trigger collection of
    sources the new user did not choose. The example keeps the runtime defaults,
    while feeds and web targets start empty for self-service setup.
    """
    path = workspace_config_path()
    if path.exists():
        return path
    module_root = Path(__file__).resolve().parents[1]
    example = module_root / "config" / "config.example.yaml"
    if not example.exists():
        raise FileNotFoundError(f"配置模板不存在：{example}")
    data = yaml.safe_load(example.read_text(encoding="utf-8")) or {}
    data.setdefault("rss", {})["feeds"] = []
    data.setdefault("web_scraper", {})["targets"] = []
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return path


def workspace_sqlite_path() -> Path:
    return workspace_root() / "dataradar.sqlite3"


def workspace_signature(value: str) -> str:
    secret = os.getenv("WORKSPACE_AUTH_SECRET", "development-only-change-me").encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()
