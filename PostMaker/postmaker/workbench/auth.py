"""Small dependency-free account and session store for the hosted MVP."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from math import ceil
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


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class AuthStore:
    LOGIN_FAILURE_LIMIT = 5
    LOGIN_LOCKOUT_SECONDS = 300

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path or _db_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000")
        conn.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS request_limits (
                    key TEXT PRIMARY KEY,
                    window_started_at TEXT NOT NULL,
                    request_count INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS login_attempts (
                    key TEXT PRIMARY KEY,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    locked_until TEXT,
                    updated_at TEXT NOT NULL
                );
            """)

    @staticmethod
    def normalize_email(email: str) -> str:
        value = email.strip().lower()
        if len(value) > 320 or not _EMAIL_RE.fullmatch(value):
            raise ValueError("请输入有效的邮箱地址")
        return value

    @staticmethod
    def _retry_after(value: str | None, now: datetime | None = None) -> int:
        if not value:
            return 0
        try:
            remaining = datetime.fromisoformat(value) - (now or _now())
            return max(0, ceil(remaining.total_seconds()))
        except ValueError:
            return 0

    def cleanup_expired(self) -> None:
        """清理过期 session 和长时间未更新的限流记录。"""
        cutoff = (_now() - timedelta(days=2)).isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (_now().isoformat(),))
            conn.execute("DELETE FROM request_limits WHERE updated_at < ?", (cutoff,))
            conn.execute("DELETE FROM login_attempts WHERE updated_at < ? AND (locked_until IS NULL OR locked_until <= ?)",
                         (cutoff, _now().isoformat()))

    def check_rate_limit(self, key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
        """在 SQLite 中原子地记录请求次数，返回 (是否允许, 等待秒数)。"""
        max_requests = max(1, int(max_requests))
        window_seconds = max(1, int(window_seconds))
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM request_limits WHERE key=?", (key,)).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO request_limits(key,window_started_at,request_count,updated_at) VALUES (?,?,?,?)",
                    (key, now.isoformat(), 1, now.isoformat()),
                )
                return True, 0
            try:
                started = datetime.fromisoformat(row["window_started_at"])
            except ValueError:
                started = now - timedelta(seconds=window_seconds)
            elapsed = (now - started).total_seconds()
            if elapsed >= window_seconds:
                conn.execute(
                    "UPDATE request_limits SET window_started_at=?,request_count=1,updated_at=? WHERE key=?",
                    (now.isoformat(), now.isoformat(), key),
                )
                return True, 0
            if row["request_count"] >= max_requests:
                return False, max(1, ceil(window_seconds - elapsed))
            conn.execute(
                "UPDATE request_limits SET request_count=request_count+1,updated_at=? WHERE key=?",
                (now.isoformat(), key),
            )
            return True, 0

    @staticmethod
    def _user(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if not row:
            return None
        return {"id": row["id"], "email": row["email"], "workspace_id": row["workspace_id"]}

    def create_user(self, email: str, password: str) -> dict[str, Any]:
        email = self.normalize_email(email)
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

    @staticmethod
    def _login_key(email: str, client_key: str | None = None) -> str:
        return f"{email}|{client_key or 'unknown'}"

    def login_lockout_remaining(self, email: str, client_key: str | None = None) -> int:
        try:
            email = self.normalize_email(email)
        except ValueError:
            return 0
        key = self._login_key(email, client_key)
        with self._connect() as conn:
            row = conn.execute("SELECT locked_until FROM login_attempts WHERE key=?", (key,)).fetchone()
        remaining = self._retry_after(row["locked_until"] if row else None)
        if row and remaining == 0 and row["locked_until"]:
            with self._connect() as conn:
                conn.execute("DELETE FROM login_attempts WHERE key=?", (key,))
        return remaining

    def _record_login_failure(self, key: str) -> int:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT failed_count FROM login_attempts WHERE key=?", (key,)).fetchone()
            count = int(row["failed_count"] if row else 0) + 1
            locked_until = None
            if count >= self.LOGIN_FAILURE_LIMIT:
                locked_until = (now + timedelta(seconds=self.LOGIN_LOCKOUT_SECONDS)).isoformat()
            conn.execute(
                "INSERT INTO login_attempts(key,failed_count,locked_until,updated_at) VALUES (?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET failed_count=excluded.failed_count,locked_until=excluded.locked_until,updated_at=excluded.updated_at",
                (key, count, locked_until, now.isoformat()),
            )
        return self._retry_after(locked_until, now)

    def _clear_login_failures(self, key: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM login_attempts WHERE key=?", (key,))

    def authenticate(self, email: str, password: str, client_key: str | None = None) -> dict[str, Any] | None:
        try:
            email = self.normalize_email(email)
        except ValueError:
            return None
        key = self._login_key(email, client_key)
        if self.login_lockout_remaining(email, client_key):
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not _check_password(password, row["password_hash"]):
            self._record_login_failure(key)
            return None
        self._clear_login_failures(key)
        return self._user(row)

    def create_session(self, user_id: int, ttl_hours: int = 168) -> tuple[str, str]:
        self.cleanup_expired()
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
                self.delete_session(raw_token)
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
