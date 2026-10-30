"""Local SQLite persistence for the single-user review workbench."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PENDING_REVIEW = "pending_review"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkbenchStore:
    def __init__(self, path: str | None = None):
        default_path = Path(__file__).resolve().parents[2] / "output" / "workbench.sqlite3"
        self.path = Path(path or os.getenv("POSTMAKER_WORKBENCH_DB", default_path))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS drafts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    material_id INTEGER NOT NULL,
                    material_json TEXT NOT NULL,
                    persona_id TEXT NOT NULL,
                    persona_name TEXT NOT NULL,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending_review',
                    model_used TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS draft_revisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    draft_id INTEGER NOT NULL REFERENCES drafts(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    body TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_drafts_status_updated
                    ON drafts(status, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_revisions_draft
                    ON draft_revisions(draft_id, id DESC);
            """)

    @staticmethod
    def _draft(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["material"] = json.loads(data.pop("material_json"))
        return data

    def create_draft(self, material: dict, persona_id: str, persona_name: str,
                     title: str, body: str, model_used: str) -> dict:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute("""
                INSERT INTO drafts (material_id, material_json, persona_id, persona_name,
                    title, body, status, model_used, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (material["id"], json.dumps(material, ensure_ascii=False), persona_id,
                  persona_name, title, body, PENDING_REVIEW, model_used, now, now))
            draft_id = cursor.lastrowid
            conn.execute("""INSERT INTO draft_revisions
                (draft_id, title, body, status, created_at) VALUES (?, ?, ?, ?, ?)""",
                (draft_id, title, body, PENDING_REVIEW, now))
        return self.get_draft(draft_id)

    def list_drafts(self, status: str | None = None, limit: int = 100) -> list[dict]:
        with self._connect() as conn:
            if status and status != "all":
                rows = conn.execute("SELECT * FROM drafts WHERE status=? ORDER BY updated_at DESC LIMIT ?",
                                    (status, limit)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM drafts ORDER BY updated_at DESC LIMIT ?",
                                    (limit,)).fetchall()
        return [self._draft(row) for row in rows]

    def get_draft(self, draft_id: int) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
        return self._draft(row) if row else None

    def update_draft(self, draft_id: int, title: str, body: str,
                     status: str | None = None) -> dict | None:
        with self._connect() as conn:
            current = conn.execute("SELECT * FROM drafts WHERE id=?", (draft_id,)).fetchone()
            if not current:
                return None
            next_status = status or current["status"]
            now = _now()
            conn.execute("UPDATE drafts SET title=?, body=?, status=?, updated_at=? WHERE id=?",
                         (title, body, next_status, now, draft_id))
            conn.execute("""INSERT INTO draft_revisions
                (draft_id, title, body, status, created_at) VALUES (?, ?, ?, ?, ?)""",
                (draft_id, title, body, next_status, now))
        return self.get_draft(draft_id)

    def list_revisions(self, draft_id: int) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("""SELECT id, draft_id, title, body, status, created_at
                FROM draft_revisions WHERE draft_id=? ORDER BY id DESC""", (draft_id,)).fetchall()
        return [dict(row) for row in rows]

    def restore_revision(self, draft_id: int, revision_id: int) -> dict | None:
        with self._connect() as conn:
            revision = conn.execute("""SELECT * FROM draft_revisions
                WHERE id=? AND draft_id=?""", (revision_id, draft_id)).fetchone()
        if not revision:
            return None
        return self.update_draft(draft_id, revision["title"], revision["body"], revision["status"])
