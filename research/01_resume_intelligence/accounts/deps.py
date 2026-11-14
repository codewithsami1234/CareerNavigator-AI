"""Resolve the signed-in person from the session cookie."""
from __future__ import annotations

from fastapi.responses import JSONResponse

from accounts.security import COOKIE_CSRF, same_secret
from accounts.service import Principal, authenticate_request


def _denied(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": "failed", "errors": [message]})


def require_user(request) -> Principal | JSONResponse:
    principal = authenticate_request(request)
    if principal is None:
        return _denied("Sign in to continue.", 401)
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        cookie = request.cookies.get(COOKIE_CSRF, "")
        header = request.headers.get("x-csrf-token", "")
        if not same_secret(cookie, header) or not same_secret(cookie, principal.csrf_token):
            return _denied("Refresh the page and try again.", 403)
    return principal
