import hashlib
import hmac
import secrets
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from football_sim.user_workspace import normalize_username


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 260_000
SESSION_TTL_DAYS = 7
SESSION_COOKIE_NAME = "football_session"


@dataclass(frozen=True)
class User:
    username: str
    display_name: str
    is_admin: bool
    is_enabled: bool


def hash_password(password: str, salt: Optional[bytes] = None, iterations: int = PASSWORD_ITERATIONS) -> str:
    salt_bytes = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt_bytes,
        iterations,
    )
    return f"{PASSWORD_ALGORITHM}${iterations}${salt_bytes.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations_text, salt_hex, digest_hex = str(encoded).split("$", 3)
        if algorithm != PASSWORD_ALGORITHM:
            return False
        iterations = int(iterations_text)
        salt = bytes.fromhex(salt_hex)
    except (TypeError, ValueError):
        return False
    expected = hash_password(password, salt=salt, iterations=iterations)
    return hmac.compare_digest(expected, encoded)


class AuthStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _init_schema(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    is_enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    token TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username)
                )
                """
            )
            conn.commit()

    def bootstrap_admin(self, username: str, password: str) -> None:
        username = normalize_username(username)
        with sqlite3.connect(self._db_path) as conn:
            existing = conn.execute(
                "SELECT username FROM users WHERE username = ?", (username,)
            ).fetchone()
            if existing:
                return
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, is_admin, is_enabled, created_at)
                VALUES (?, ?, ?, 1, 1, ?)
                """,
                (username, username, hash_password(password), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def create_user(self, username: str, password: str) -> User:
        username = normalize_username(username)
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO users (username, display_name, password_hash, is_admin, is_enabled, created_at)
                VALUES (?, ?, ?, 0, 1, ?)
                """,
                (username, username, hash_password(password), now),
            )
            conn.commit()
        return User(username=username, display_name=username, is_admin=False, is_enabled=True)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        username = normalize_username(username)
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? AND is_enabled = 1", (username,)
            ).fetchone()
            if not row:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            return User(
                username=row["username"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                is_enabled=bool(row["is_enabled"]),
            )

    def create_session(self, username: str) -> str:
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=SESSION_TTL_DAYS)
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "INSERT INTO sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (token, username, now.isoformat(), expires.isoformat()),
            )
            conn.commit()
        return token

    def get_session_user(self, token: str) -> Optional[User]:
        if not token:
            return None
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                """
                SELECT u.* FROM sessions s
                JOIN users u ON s.username = u.username
                WHERE s.token = ? AND s.expires_at > ? AND u.is_enabled = 1
                """,
                (token, datetime.now(timezone.utc).isoformat()),
            ).fetchone()
            if not row:
                return None
            return User(
                username=row["username"],
                display_name=row["display_name"],
                is_admin=bool(row["is_admin"]),
                is_enabled=bool(row["is_enabled"]),
            )

    def delete_session(self, token: str) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.commit()

    def delete_expired_sessions(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                "DELETE FROM sessions WHERE expires_at < ?",
                (datetime.now(timezone.utc).isoformat(),),
            )
            conn.commit()
