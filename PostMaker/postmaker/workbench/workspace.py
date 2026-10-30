"""Request scoped workspace context for the hosted workbench."""

from __future__ import annotations

import os
import re
from contextvars import ContextVar
from pathlib import Path

_WORKSPACE = ContextVar("postmaker_workspace_id", default="default")
_VALID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{7,95}$")


def set_workspace_id(value: str):
    value = (value or "default").strip()
    if value != "default" and not _VALID.fullmatch(value):
        raise ValueError("workspace id 无效")
    return _WORKSPACE.set(value)


def reset_workspace(token) -> None:
    _WORKSPACE.reset(token)


def workspace_id() -> str:
    return _WORKSPACE.get()


def workspace_db_path() -> Path:
    root = Path(os.getenv("POSTMAKER_WORKSPACES_DIR", "output/workspaces"))
    return root / workspace_id() / "workbench.sqlite3"
