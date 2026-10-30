"""Request-scoped workspace paths for hosted, multi-user local mode."""

from __future__ import annotations

import os
import re
from contextvars import ContextVar
from pathlib import Path

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


def workspace_sqlite_path() -> Path:
    return workspace_root() / "dataradar.sqlite3"
