"""Small dependency-free account and session store for the hosted MVP."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


def _db_path() -> Path:
    default = Path(__file__).resolve().parents[2] / "output" / "auth.sqlite3"
    path = Path(os.getenv("POSTMAKER_AUTH_DB", default))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${salt.hex()}${digest.hex()}"


def _check_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


class AuthStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or _db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    workspace_id TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    csrf_token TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token_hash);
            """)

    @staticmethod
    def _user(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {"id": row["id"], "email": row["email"], "workspace_id": row["workspace_id"]}

    def create_user(self, email: str, password: str) -> dict[str, Any]:
        email = email.strip().lower()
        if len(email) > 320 or "@" not in email:
            raise ValueError("请输入有效的邮箱地址")
        if len(password) < 8 or len(password) > 200:
            raise ValueError("密码长度应为 8 到 200 个字符")
        workspace = f"ws_{uuid4().hex}"
        try:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO users(email,password_hash,workspace_id,created_at) VALUES (?,?,?,?)",
                    (email, _hash_password(password), workspace, _now().isoformat()),
                )
                user_id = cur.lastrowid
        except sqlite3.IntegrityError as exc:
            raise ValueError("该邮箱已经注册") from exc
        return {"id": user_id, "email": email, "workspace_id": workspace}

    def authenticate(self, email: str, password: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not row or not _check_password(password, row["password_hash"]):
            return None
        return self._user(row)

    def create_session(self, user_id: int, ttl_hours: int = 168) -> tuple[str, str]:
        raw = secrets.token_urlsafe(48)
        csrf = secrets.token_urlsafe(24)
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions(user_id,token_hash,csrf_token,expires_at,created_at) VALUES (?,?,?,?,?)",
                (user_id, hashlib.sha256(raw.encode()).hexdigest(), csrf,
                 (now + timedelta(hours=ttl_hours)).isoformat(), now.isoformat()),
            )
        return raw, csrf

    def get_session(self, raw_token: str | None) -> tuple[dict[str, Any], str] | None:
        if not raw_token:
            return None
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        with self._connect() as conn:
            row = conn.execute("""
                SELECT s.csrf_token, s.expires_at, u.id, u.email, u.workspace_id
                FROM sessions s JOIN users u ON u.id=s.user_id
                WHERE s.token_hash=?
            """, (token_hash,)).fetchone()
        if not row:
            return None
        try:
            if datetime.fromisoformat(row["expires_at"]) <= _now():
                return None
        except ValueError:
            return None
        return ({"id": row["id"], "email": row["email"], "workspace_id": row["workspace_id"]}, row["csrf_token"])

    def delete_session(self, raw_token: str | None) -> None:
        if not raw_token:
            return
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(raw_token.encode()).hexdigest(),))


def auth_required() -> bool:
    return os.getenv("POSTMAKER_AUTH_REQUIRED", "0").lower() in {"1", "true", "yes"}


def workspace_signature(workspace: str) -> str:
    secret = os.getenv("WORKSPACE_AUTH_SECRET", "development-only-change-me").encode()
    return hmac.new(secret, workspace.encode(), hashlib.sha256).hexdigest()
