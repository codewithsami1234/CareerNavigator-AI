"""Registration and server-side sessions.

The signed-in person is taken from the session cookie. A user id in the
request body is never read.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta

from sqlalchemy import update

from accounts.db import aware, session_scope, utcnow
from accounts.models import Session, User
from accounts.security import (
    GENERIC_LOGIN,
    SESSION_SECONDS,
    hash_password,
    hash_token,
    new_token,
    verify_password,
)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
LOGIN_LIMIT = 8
LOGIN_WINDOW = timedelta(minutes=15)
_failures: dict[str, list[datetime]] = {}


class Principal:
    def __init__(self, user: User, session_row: Session):
        self.id = user.id
        self.email = user.email
        self.name = user.full_name
        self.session_id = session_row.id
        self.csrf_token = session_row.csrf_token

    def public(self) -> dict:
        return {"name": self.name, "email": self.email}


class Result:
    def __init__(
        self,
        status_code: int,
        payload: dict,
        session_token: str | None = None,
        csrf_token: str | None = None,
        max_age: int | None = None,
        clear_session: bool = False,
    ):
        self.status_code = status_code
        self.payload = payload
        self.session_token = session_token
        self.csrf_token = csrf_token
        self.max_age = max_age
        self.clear_session = clear_session


def reset_login_limits() -> None:
    _failures.clear()


def new_id() -> str:
    return str(uuid.uuid4())


def normalize_email(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        return None
    return email


def clean_name(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    name = " ".join(value.split())
    if not name or len(name) > 80 or re.search(r"[\x00-\x1f\x7f]", name):
        return None
    return name


def password_problem(password: object, email: str) -> str | None:
    if not isinstance(password, str) or len(password) < 8 or len(password) > 200:
        return "Use at least 8 characters."
    if password.lower() == email.lower():
        return "Choose a password that is not your email address."
    return None


def _failed(status_code: int, message: str) -> Result:
    return Result(status_code, {"status": "failed", "errors": [message]})


def _limit_key(email: str, ip: str) -> str:
    return hash_token(f"login|{email}|{ip}")


def _recent_failures(email: str, ip: str) -> list[datetime]:
    now = utcnow()
    recent = [item for item in _failures.get(_limit_key(email, ip), []) if now - item < LOGIN_WINDOW]
    _failures[_limit_key(email, ip)] = recent
    return recent


def _too_many(email: str, ip: str) -> bool:
    return len(_recent_failures(email, ip)) >= LOGIN_LIMIT


def _note_failure(email: str, ip: str) -> None:
    recent = _recent_failures(email, ip)
    recent.append(utcnow())
    _failures[_limit_key(email, ip)] = recent


def _issue_session(db, user: User, presented_token: str | None) -> tuple[str, str, int]:
    if presented_token:
        previous = db.query(Session).filter(Session.token_hash == hash_token(presented_token)).one_or_none()
        if previous is not None and previous.revoked_at is None:
            previous.revoked_at = utcnow()
    raw = new_token()
    csrf = new_token()
    db.add(
        Session(
            id=new_id(),
            user_id=user.id,
            token_hash=hash_token(raw),
            csrf_token=csrf,
            expires_at=utcnow() + timedelta(seconds=SESSION_SECONDS),
            revoked_at=None,
            created_at=utcnow(),
        )
    )
    return raw, csrf, SESSION_SECONDS


def _revoke_all(db, user_id: str) -> None:
    db.execute(
        update(Session)
        .where(Session.user_id == user_id, Session.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


def _public(user: User) -> dict:
    return {"name": user.full_name, "email": user.email}


def register(payload: dict) -> Result:
    email = normalize_email(payload.get("email"))
    name = clean_name(payload.get("full_name") if payload.get("full_name") is not None else payload.get("name"))
    password = payload.get("password")
    confirm = payload.get("confirm_password")
    if name is None:
        return _failed(400, "Enter your name.")
    if email is None:
        return _failed(400, "Enter a valid email address.")
    problem = password_problem(password, email)
    if problem:
        return _failed(400, problem)
    if password != confirm:
        return _failed(400, "The passwords do not match.")
    with session_scope() as db:
        existing = db.query(User).filter(User.email == email).one_or_none()
        if existing is not None:
            return _failed(409, "An account with this email already exists.")
        user = User(
            id=new_id(),
            full_name=name,
            email=email,
            password_hash=hash_password(str(password)),
            created_at=utcnow(),
        )
        db.add(user)
        db.flush()
        raw, csrf, max_age = _issue_session(db, user, None)
        public = _public(user)
    return Result(
        200,
        {"status": "created", "user": public},
        session_token=raw,
        csrf_token=csrf,
        max_age=max_age,
    )


def login(email_value: object, password: object, ip: str, presented_session: str | None) -> Result:
    email = normalize_email(email_value)
    if email is None or not isinstance(password, str):
        return _failed(401, GENERIC_LOGIN)
    if _too_many(email, ip):
        return _failed(429, "Too many sign-in attempts. Wait a few minutes and try again.")
    with session_scope() as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        stored = user.password_hash if user is not None else None
        if not verify_password(stored, password) or user is None:
            _note_failure(email, ip)
            return _failed(401, GENERIC_LOGIN)
        raw, csrf, max_age = _issue_session(db, user, presented_session)
        public = _public(user)
    return Result(
        200,
        {"status": "signed_in", "user": public},
        session_token=raw,
        csrf_token=csrf,
        max_age=max_age,
    )


def logout(presented_session: str | None) -> Result:
    if presented_session:
        with session_scope() as db:
            row = db.query(Session).filter(Session.token_hash == hash_token(presented_session)).one_or_none()
            if row is not None and row.revoked_at is None:
                row.revoked_at = utcnow()
    return Result(
        200,
        {"status": "signed_out"},
        csrf_token=new_token(),
        clear_session=True,
        max_age=SESSION_SECONDS,
    )


def authenticate_request(request) -> Principal | None:
    raw = request.cookies.get("cn_session", "")
    if not raw:
        return None
    with session_scope() as db:
        row = db.query(Session).filter(Session.token_hash == hash_token(raw)).one_or_none()
        if row is None or row.revoked_at is not None or aware(row.expires_at) <= utcnow():
            return None
        user = db.get(User, row.user_id)
        if user is None:
            return None
        return Principal(user, row)


def change_password(principal: Principal, current: object, password: object, confirm: object) -> Result:
    with session_scope() as db:
        user = db.get(User, principal.id)
        offered = current if isinstance(current, str) else ""
        if user is None or not verify_password(user.password_hash, offered):
            return _failed(400, "The current password is not correct.")
        problem = password_problem(password, user.email)
        if problem:
            return _failed(400, problem)
        if password != confirm:
            return _failed(400, "The passwords do not match.")
        if isinstance(password, str) and verify_password(user.password_hash, password):
            return _failed(400, "Choose a different password.")
        user.password_hash = hash_password(str(password))
        _revoke_all(db, user.id)
        raw, csrf, max_age = _issue_session(db, user, None)
    return Result(
        200,
        {"status": "updated", "message": "Your password was updated."},
        session_token=raw,
        csrf_token=csrf,
        max_age=max_age,
    )


def update_profile(principal: Principal, name_value: object) -> Result:
    name = clean_name(name_value)
    if name is None:
        return _failed(400, "Enter your name.")
    with session_scope() as db:
        user = db.get(User, principal.id)
        if user is None:
            return _failed(401, "Sign in to continue.")
        user.full_name = name
        public = _public(user)
    return Result(200, {"status": "updated", "user": public})


def user_count() -> int:
    with session_scope() as db:
        return db.query(User).count()


def user_by_email(email: str) -> User | None:
    with session_scope() as db:
        user = db.query(User).filter(User.email == email).one_or_none()
        if user is None:
            return None
        db.expunge(user)
        return user
