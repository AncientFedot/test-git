from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from dataclasses import dataclass


@dataclass
class AuthenticatedUser:
    user_id: int
    login: str
    role: str


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, salt_b64, hash_b64 = stored_hash.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(hash_b64)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return hmac.compare_digest(digest, expected)


def _sign(payload: str, secret: str) -> str:
    sig = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(sig).decode("ascii")


def issue_token(conn: sqlite3.Connection, login: str, password: str, ttl_seconds: int = 3600) -> str | None:
    row = conn.execute(
        "SELECT id, login, role, password_hash, is_active FROM users WHERE login = ?",
        (login,),
    ).fetchone()
    if row is None or int(row["is_active"]) != 1:
        return None
    if not verify_password(password, row["password_hash"]):
        return None

    secret = os.getenv("BONIFACIY_API_SIGNING_KEY", os.getenv("BONIFACIY_SECRET_KEY", ""))
    if not secret:
        return None

    exp = int(time.time()) + ttl_seconds
    nonce = secrets.token_hex(8)
    payload = f"{row['id']}:{row['login']}:{row['role']}:{exp}:{nonce}"
    signature = _sign(payload, secret)
    token = base64.urlsafe_b64encode(f"{payload}:{signature}".encode("utf-8")).decode("ascii")
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    conn.execute(
        """
        INSERT INTO api_sessions(user_id, token_hash, expires_at, is_revoked)
        VALUES(?, ?, datetime(?, 'unixepoch'), 0)
        """,
        (int(row["id"]), token_hash, exp),
    )
    conn.commit()
    return token


def authenticate_token(conn: sqlite3.Connection, token: str) -> AuthenticatedUser | None:
    secret = os.getenv("BONIFACIY_API_SIGNING_KEY", os.getenv("BONIFACIY_SECRET_KEY", ""))
    if not secret:
        return None

    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        parts = decoded.split(":")
        user_id, login, role, exp, nonce = parts[0], parts[1], parts[2], parts[3], parts[4]
        signature = parts[5]
    except Exception:
        return None

    payload = f"{user_id}:{login}:{role}:{exp}:{nonce}"
    if not hmac.compare_digest(signature, _sign(payload, secret)):
        return None

    if int(exp) < int(time.time()):
        return None

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = conn.execute(
        """
        SELECT s.user_id, u.login, u.role
        FROM api_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.is_revoked = 0
          AND s.expires_at > CURRENT_TIMESTAMP
        """,
        (token_hash,),
    ).fetchone()
    if row is None:
        return None
    return AuthenticatedUser(user_id=int(row["user_id"]), login=row["login"], role=row["role"])


def revoke_sessions(conn: sqlite3.Connection, user_id: int | None = None) -> int:
    if user_id is None:
        cur = conn.execute("UPDATE api_sessions SET is_revoked = 1 WHERE is_revoked = 0")
    else:
        cur = conn.execute("UPDATE api_sessions SET is_revoked = 1 WHERE is_revoked = 0 AND user_id = ?", (user_id,))
    conn.commit()
    return int(cur.rowcount)


def generate_signing_key() -> str:
    return secrets.token_urlsafe(48)
