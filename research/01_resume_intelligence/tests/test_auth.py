"""Registration, sessions, and account isolation."""
from __future__ import annotations

import sqlite3
from datetime import timedelta

from fastapi.testclient import TestClient

from accounts.db import prepare_database, reset_engine, session_scope, utcnow
from accounts.models import Record, Session
from accounts.security import hash_token, verify_password
from accounts.service import user_by_email, user_count
from api.app import create_app
from testing_api import PASSWORD, open_client

ORIGIN = "http://localhost:5173"


def _app():
    return TestClient(create_app(), raise_server_exceptions=False)


def _csrf(client: TestClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200, response.text
    return client.cookies.get("cn_csrf", "")


def _replace_cookies(client: TestClient, response) -> str:
    """Keep the newest session cookie when a response both clears and sets one."""
    session = ""
    csrf = client.cookies.get("cn_csrf", "")
    for header in response.headers.get_list("set-cookie"):
        if header.lower().startswith("cn_csrf="):
            csrf = header.split(";", 1)[0].split("=", 1)[1]
        if header.lower().startswith("cn_session=") and "max-age=0" not in header.lower():
            session = header.split(";", 1)[0].split("=", 1)[1]
    client.cookies.clear()
    if session:
        client.cookies.set("cn_session", session)
    if csrf:
        client.cookies.set("cn_csrf", csrf)
    return session


def _post(client: TestClient, path: str, payload: dict):
    return client.post(path, json=payload, headers={"X-CSRF-Token": client.cookies.get("cn_csrf", "")})


def _register(client: TestClient, email="ada@example.com", password=PASSWORD, name="Ada Lovelace", **extra):
    _csrf(client)
    body = {
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": extra.get("confirm_password", password),
    }
    return _post(client, "/api/auth/register", body)


class TestRegistration:
    def test_successful_registration_hashes_the_password_and_signs_in(self, tmp_path):
        client = _app()
        response = _register(client)
        assert response.status_code == 200, response.text
        assert response.json()["user"]["name"] == "Ada Lovelace"
        assert PASSWORD not in response.text
        restored = client.get("/api/auth/session")
        assert restored.status_code == 200
        assert restored.json()["user"]["email"] == "ada@example.com"
        user = user_by_email("ada@example.com")
        assert user is not None
        assert user.full_name == "Ada Lovelace"
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert verify_password(user.password_hash, PASSWORD) is True
        blob = (tmp_path / "auth.sqlite").read_bytes()
        assert PASSWORD.encode() not in blob
        assert client.cookies.get("cn_session").encode() not in blob

    def test_invalid_email_is_rejected(self):
        response = _register(_app(), email="not-an-email")
        assert response.status_code == 400
        assert response.json()["errors"] == ["Enter a valid email address."]
        assert user_count() == 0

    def test_duplicate_account_does_not_create_a_second_user(self):
        client = _app()
        first = _register(client)
        assert first.status_code == 200, first.text
        again = _register(client)
        assert again.status_code == 409
        assert again.json()["errors"] == ["An account with this email already exists."]
        assert user_count() == 1

    def test_short_password_is_rejected(self):
        client = _app()
        short = _register(client, password="short1", confirm_password="short1")
        assert short.status_code == 400
        assert "8" in short.json()["errors"][0]
        mismatch = _register(client, password=PASSWORD, confirm_password="Other-Password-12")
        assert mismatch.status_code == 400
        assert user_count() == 0

    def test_a_supplied_user_id_is_ignored(self):
        client = _app()
        _csrf(client)
        response = _post(
            client,
            "/api/auth/register",
            {
                "name": "Ada Lovelace",
                "email": "ada@example.com",
                "password": PASSWORD,
                "confirm_password": PASSWORD,
                "user_id": "11111111-1111-1111-1111-111111111111",
            },
        )
        assert response.status_code == 200, response.text
        user = user_by_email("ada@example.com")
        assert user is not None
        assert user.id != "11111111-1111-1111-1111-111111111111"


class TestAuthentication:
    def test_successful_login_rotates_the_session_and_restores_it(self):
        client = _app()
        assert _register(client).status_code == 200
        planted = "attacker-chosen-token-value"
        client.cookies.set("cn_session", planted)
        response = _post(client, "/api/auth/login", {"email": "ada@example.com", "password": PASSWORD})
        assert response.status_code == 200, response.text
        assert response.json()["user"]["email"] == "ada@example.com"
        issued = _replace_cookies(client, response)
        assert issued and issued != planted
        assert "httponly" in ",".join(response.headers.get_list("set-cookie")).lower()
        restored = client.get("/api/auth/session")
        assert restored.status_code == 200
        assert restored.json()["user"]["name"] == "Ada Lovelace"
        other = _app()
        other.cookies.set("cn_session", planted)
        assert other.get("/api/auth/session").status_code == 401

    def test_incorrect_password_matches_an_unknown_email(self):
        client = _app()
        assert _register(client).status_code == 200
        wrong = _post(client, "/api/auth/login", {"email": "ada@example.com", "password": "Wrong-Password-12"})
        missing = _post(client, "/api/auth/login", {"email": "nobody@example.com", "password": "Wrong-Password-12"})
        assert wrong.status_code == missing.status_code == 401
        assert wrong.json() == missing.json()
        assert "ada@example.com" not in wrong.text

    def test_logout_revokes_the_server_session(self):
        client = _app()
        assert _register(client).status_code == 200
        raw = client.cookies.get("cn_session")
        assert _post(client, "/api/auth/logout", {}).status_code == 200
        assert client.get("/api/auth/session").status_code == 401
        revived = _app()
        revived.cookies.set("cn_session", raw)
        assert revived.get("/api/auth/session").status_code == 401

    def test_expired_session_is_rejected(self):
        client = _app()
        assert _register(client).status_code == 200
        raw = client.cookies.get("cn_session")
        with session_scope() as db:
            row = db.query(Session).filter(Session.token_hash == hash_token(raw)).one()
            row.expires_at = utcnow() - timedelta(minutes=5)
        assert client.get("/api/auth/session").status_code == 401

    def test_change_password_revokes_the_previous_session(self):
        client = _app()
        assert _register(client).status_code == 200
        old = client.cookies.get("cn_session")
        rejected = _post(
            client,
            "/api/auth/change-password",
            {"current_password": "Wrong-Password-12", "password": "Updated-Password-12", "confirm_password": "Updated-Password-12"},
        )
        assert rejected.status_code == 400
        assert verify_password(user_by_email("ada@example.com").password_hash, PASSWORD) is True
        updated = _post(
            client,
            "/api/auth/change-password",
            {"current_password": PASSWORD, "password": "Updated-Password-12", "confirm_password": "Updated-Password-12"},
        )
        assert updated.status_code == 200, updated.text
        _replace_cookies(client, updated)
        assert client.get("/api/auth/session").status_code == 200
        stale = _app()
        stale.cookies.set("cn_session", old)
        assert stale.get("/api/auth/session").status_code == 401
        fresh = _app()
        _csrf(fresh)
        signed = _post(fresh, "/api/auth/login", {"email": "ada@example.com", "password": "Updated-Password-12"})
        assert signed.status_code == 200

    def test_login_rate_limit(self):
        client = _app()
        assert _register(client).status_code == 200
        for _ in range(8):
            failed = _post(client, "/api/auth/login", {"email": "ada@example.com", "password": "Wrong-Password-12"})
            assert failed.status_code == 401
        blocked = _post(client, "/api/auth/login", {"email": "ada@example.com", "password": PASSWORD})
        assert blocked.status_code == 429


class TestMigration:
    def test_existing_user_rows_are_kept(self, tmp_path):
        path = tmp_path / "auth.sqlite"
        connection = sqlite3.connect(path)
        connection.execute(
            """
            CREATE TABLE users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                email_verified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, NULL, ?, ?)",
            ("user-1", "ada@example.com", "Ada Lovelace", "$argon2id$kept", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        connection.execute(
            """
            CREATE TABLE sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                remember INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO sessions VALUES ('session-1', 'user-1', 'hashed-token', 'csrf', '2026-12-01T00:00:00+00:00', NULL, 1, '2026-01-01T00:00:00+00:00')"
        )
        connection.execute(
            """
            CREATE TABLE records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO records VALUES ('record-1', 'user-1', 'resume', '{\"kept\":true}', '2026-01-01T00:00:00+00:00')"
        )
        connection.execute(
            "CREATE TABLE email_tokens (id TEXT PRIMARY KEY, user_id TEXT, purpose TEXT, token_hash TEXT, expires_at TEXT, used_at TEXT)"
        )
        connection.execute("INSERT INTO email_tokens VALUES ('token-1', 'user-1', 'verify', 'secret-hash', '2026-01-02', NULL)")
        connection.commit()
        connection.close()

        reset_engine()
        prepare_database()
        user = user_by_email("ada@example.com")
        assert user is not None
        assert user.id == "user-1"
        assert user.full_name == "Ada Lovelace"
        assert user.password_hash == "$argon2id$kept"
        with session_scope() as db:
            assert db.get(Session, "session-1") is not None
            assert db.get(Record, "record-1") is not None
        inspected = sqlite3.connect(path)
        tables = {row[0] for row in inspected.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        columns = [row[1] for row in inspected.execute("PRAGMA table_info(users)")]
        inspected.close()
        assert "email_tokens" not in tables
        assert "login_attempts" not in tables
        assert columns == ["id", "full_name", "email", "password_hash", "created_at"]


class TestAuthorization:
    def test_analysis_requires_a_session_and_keeps_health_public(self):
        client = _app()
        health = client.get("/api/health", headers={"Origin": ORIGIN})
        assert health.status_code == 200
        assert health.headers["access-control-allow-origin"] == ORIGIN
        _csrf(client)
        resume = client.post(
            "/api/resume",
            files={"file": ("a.txt", b"Python developer", "text/plain")},
            headers={"X-CSRF-Token": client.cookies.get("cn_csrf", "")},
        )
        assert resume.status_code == 401
        assert "Traceback" not in resume.text
        assert "sqlite" not in resume.text.lower()

    def test_signed_in_analysis_is_allowed(self):
        client = open_client()
        response = client.post(
            "/api/resume",
            files={"file": ("a.txt", b"Python developer with SQL experience", "text/plain")},
        )
        assert response.status_code == 200

    def test_users_cannot_read_each_others_records_or_workspace(self):
        ada = open_client("ada@example.com", "Ada Lovelace")
        grace = open_client("grace@example.com", "Grace Hopper")
        uploaded = ada.post(
            "/api/resume",
            files={"file": ("ada.txt", b"Skills: Python, SQL\nExperience\nBuilt tools with Python.", "text/plain")},
        )
        assert uploaded.status_code == 200, uploaded.text
        report = ada.post("/api/report", json={"resume": uploaded.json(), "job_title": "Ada only title"})
        assert report.status_code == 200, report.text
        saved = ada.put("/api/me/workspace", json={"workspace": {"note": "ADA-PRIVATE-NOTE"}})
        assert saved.status_code == 200, saved.text
        records = ada.get("/api/records").json()["records"]
        assert records
        for item in records:
            assert grace.get(f"/api/records/{item['id']}").status_code == 404
            assert item["id"] not in grace.get("/api/records").text
            assert grace.delete(f"/api/records/{item['id']}").status_code == 404
        assert ada.get(f"/api/records/{records[0]['id']}").status_code == 200
        foreign = grace.get("/api/me/workspace")
        assert foreign.status_code == 200
        assert foreign.json()["workspace"] is None
        assert "ADA-PRIVATE-NOTE" not in foreign.text

    def test_missing_csrf_is_rejected_and_the_session_remains(self):
        client = open_client()
        response = client.client.post("/api/auth/logout")
        assert response.status_code == 403
        assert client.get("/api/auth/session").status_code == 200
