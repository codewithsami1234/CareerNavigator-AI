"""SQLite account storage.

``create_all`` adds missing tables and does not drop existing ones.
An older account file is reshaped in place. User rows, sessions, saved
analysis, and workspaces are copied. Email-token and sign-in-attempt
tables are removed because those features are gone.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

from accounts.models import Base

_engine = None
_factory = None
_url = None

MIGRATION_VERSIONS = ("001_accounts", "002_simple_accounts")
USER_COLUMNS = {"id", "full_name", "email", "password_hash", "created_at"}
SESSION_COLUMNS = {"id", "user_id", "token_hash", "csrf_token", "expires_at", "revoked_at", "created_at"}


def database_url() -> str:
    configured = os.environ.get("CAREERNAV_DATABASE_URL", "").strip()
    if configured.startswith("sqlite"):
        return configured
    root = Path(__file__).resolve().parent.parent
    path = root / "data" / "careernavigator.sqlite"
    return "sqlite:///" + path.as_posix()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return _as_utc(value)


def reset_engine() -> None:
    """Drop the cached engine so tests can point at a fresh database."""
    global _engine, _factory, _url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _factory = None
    _url = None


def _tables(cursor) -> set[str]:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def _columns(cursor, table: str) -> list[str]:
    cursor.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def _rebuild_users(cursor, columns: list[str]) -> None:
    if "full_name" in columns and "name" in columns:
        name_sql = "COALESCE(NULLIF(TRIM(full_name), ''), NULLIF(TRIM(name), ''), 'Account')"
    elif "full_name" in columns:
        name_sql = "COALESCE(NULLIF(TRIM(full_name), ''), 'Account')"
    else:
        name_sql = "COALESCE(NULLIF(TRIM(name), ''), 'Account')"
    before = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    cursor.execute("DROP TABLE IF EXISTS users_simple")
    cursor.execute(
        """
        CREATE TABLE users_simple (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            full_name VARCHAR(80) NOT NULL,
            email VARCHAR(254) NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL
        )
        """
    )
    cursor.execute(
        f"""
        INSERT INTO users_simple (id, full_name, email, password_hash, created_at)
        SELECT id, {name_sql}, email, password_hash, created_at FROM users
        """
    )
    after = cursor.execute("SELECT COUNT(*) FROM users_simple").fetchone()[0]
    if before != after:
        raise RuntimeError("The account migration stopped because the user count would change.")
    cursor.execute("DROP TABLE users")
    cursor.execute("ALTER TABLE users_simple RENAME TO users")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users (email)")


def _rebuild_sessions(cursor) -> None:
    before = cursor.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    columns = set(_columns(cursor, "sessions"))
    revoked = "revoked_at" if "revoked_at" in columns else "NULL"
    cursor.execute("DROP TABLE IF EXISTS sessions_simple")
    cursor.execute(
        """
        CREATE TABLE sessions_simple (
            id VARCHAR(36) NOT NULL PRIMARY KEY,
            user_id VARCHAR(36) NOT NULL,
            token_hash VARCHAR(64) NOT NULL,
            csrf_token VARCHAR(64) NOT NULL,
            expires_at DATETIME NOT NULL,
            revoked_at DATETIME,
            created_at DATETIME NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users (id)
        )
        """
    )
    cursor.execute(
        f"""
        INSERT INTO sessions_simple (id, user_id, token_hash, csrf_token, expires_at, revoked_at, created_at)
        SELECT id, user_id, token_hash, csrf_token, expires_at, {revoked}, created_at FROM sessions
        """
    )
    after = cursor.execute("SELECT COUNT(*) FROM sessions_simple").fetchone()[0]
    if before != after:
        raise RuntimeError("The account migration stopped because the session count would change.")
    cursor.execute("DROP TABLE sessions")
    cursor.execute("ALTER TABLE sessions_simple RENAME TO sessions")
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_sessions_token_hash ON sessions (token_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_sessions_user_id ON sessions (user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS ix_sessions_expires_at ON sessions (expires_at)")


def _apply_simple_schema(cursor) -> None:
    tables = _tables(cursor)
    if "users_simple" in tables and "users" not in tables:
        cursor.execute("ALTER TABLE users_simple RENAME TO users")
        tables = _tables(cursor)
    if "users" in tables and set(_columns(cursor, "users")) != USER_COLUMNS:
        _rebuild_users(cursor, _columns(cursor, "users"))
    if "sessions" in tables and set(_columns(cursor, "sessions")) != SESSION_COLUMNS:
        _rebuild_sessions(cursor)
    cursor.execute("DROP TABLE IF EXISTS email_tokens")
    cursor.execute("DROP TABLE IF EXISTS login_attempts")


def simplify_existing_schema(engine) -> None:
    """Copy older account rows into the smaller SQLite tables."""
    raw = engine.raw_connection()
    dbapi = getattr(raw, "driver_connection", raw)
    previous = dbapi.isolation_level
    try:
        dbapi.isolation_level = None
        setup = dbapi.cursor()
        setup.execute("PRAGMA foreign_keys=OFF")
        setup.close()
        dbapi.isolation_level = ""
        cursor = dbapi.cursor()
        cursor.execute("BEGIN")
        try:
            _apply_simple_schema(cursor)
            cursor.execute("COMMIT")
        except Exception:
            cursor.execute("ROLLBACK")
            raise
        dbapi.isolation_level = None
        done = dbapi.cursor()
        done.execute("PRAGMA foreign_keys=ON")
        done.close()
    finally:
        dbapi.isolation_level = previous
        raw.close()


def get_engine():
    global _engine, _factory, _url
    url = database_url()
    if _engine is not None and _url == url:
        return _engine
    reset_engine()
    if url.startswith("sqlite:///"):
        file_part = url.removeprefix("sqlite:///")
        if file_part and file_part != ":memory:":
            Path(file_part).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True, future=True)

    @event.listens_for(engine, "connect")
    def _foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    simplify_existing_schema(engine)
    applied = utcnow().isoformat()
    with engine.begin() as connection:
        for version in MIGRATION_VERSIONS:
            connection.execute(
                text(
                    "INSERT OR IGNORE INTO schema_migrations (version, applied_at) "
                    "VALUES (:version, :applied)"
                ),
                {"version": version, "applied": applied},
            )
    _engine = engine
    _factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    _url = url
    return engine


def prepare_database() -> None:
    get_engine()


@contextmanager
def session_scope():
    get_engine()
    if _factory is None:
        raise RuntimeError("database factory was not created")
    db = _factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
