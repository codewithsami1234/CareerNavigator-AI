"""Password hashing and random session tokens.

Passwords use Argon2id. Session tokens are random, and only their SHA-256
hashes are written to the database.
"""
from __future__ import annotations

import hashlib
import os
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

COOKIE_SESSION = "cn_session"
COOKIE_CSRF = "cn_csrf"
GENERIC_LOGIN = "The email or password is not correct."
SESSION_SECONDS = 14 * 24 * 60 * 60

_DUMMY: tuple[int, int, str] | None = None


def cookie_secure() -> bool:
    return os.environ.get("CAREERNAV_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes"}


def _hasher() -> PasswordHasher:
    memory = int(os.environ.get("CAREERNAV_ARGON_MEMORY", "19456"))
    time_cost = int(os.environ.get("CAREERNAV_ARGON_TIME", "2"))
    return PasswordHasher(time_cost=time_cost, memory_cost=memory, parallelism=1, hash_len=32, salt_len=16)


def hash_password(password: str) -> str:
    return _hasher().hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    """Return whether the password matches. A missing hash still runs Argon2."""
    global _DUMMY
    memory = int(os.environ.get("CAREERNAV_ARGON_MEMORY", "19456"))
    time_cost = int(os.environ.get("CAREERNAV_ARGON_TIME", "2"))
    if _DUMMY is None or _DUMMY[0] != memory or _DUMMY[1] != time_cost:
        _DUMMY = (memory, time_cost, _hasher().hash("not-a-real-account-password"))
    candidate = stored_hash or _DUMMY[2]
    try:
        _hasher().verify(candidate, password)
    except (VerificationError, InvalidHashError):
        return False
    return stored_hash is not None


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def same_secret(left: str, right: str) -> bool:
    if not left or not right or len(left) != len(right):
        return False
    return secrets.compare_digest(left, right)
