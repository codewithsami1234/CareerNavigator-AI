"""Signed-in API client for tests that call analysis routes.

This signs in through the real registration route.
It does not disable authentication.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import create_app

PASSWORD = "Workspace-User-12"


class SignedClient:
    """Adds the CSRF header from the cookie on every unsafe request."""

    def __init__(self, client: TestClient):
        self.client = client

    def _headers(self, headers):
        merged = dict(headers or {})
        merged.setdefault("X-CSRF-Token", self.client.cookies.get("cn_csrf", ""))
        return merged

    def post(self, url, **kwargs):
        headers = self._headers(kwargs.pop("headers", None))
        return self.client.post(url, headers=headers, **kwargs)

    def put(self, url, **kwargs):
        headers = self._headers(kwargs.pop("headers", None))
        return self.client.put(url, headers=headers, **kwargs)

    def delete(self, url, **kwargs):
        headers = self._headers(kwargs.pop("headers", None))
        return self.client.delete(url, headers=headers, **kwargs)

    def get(self, url, **kwargs):
        return self.client.get(url, **kwargs)


def open_client(email: str = "workspace.user@example.com", name: str = "Workspace User") -> SignedClient:
    client = TestClient(create_app(), raise_server_exceptions=False)
    issued = client.get("/api/auth/csrf")
    assert issued.status_code == 200, issued.text
    csrf = client.cookies.get("cn_csrf", "")
    created = client.post(
        "/api/auth/register",
        json={
            "name": name,
            "email": email,
            "password": PASSWORD,
            "confirm_password": PASSWORD,
        },
        headers={"X-CSRF-Token": csrf},
    )
    assert created.status_code == 200, created.text
    assert created.json()["user"]["email"] == email
    return SignedClient(client)
