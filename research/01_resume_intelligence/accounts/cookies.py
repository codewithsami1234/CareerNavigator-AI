"""Cookie flags for the session and the CSRF token."""
from __future__ import annotations

from fastapi.responses import JSONResponse

from accounts.security import COOKIE_CSRF, COOKIE_SESSION, SESSION_SECONDS, cookie_secure
from accounts.service import Result


def _csrf(response: JSONResponse, token: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_CSRF,
        token,
        max_age=max_age,
        httponly=False,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def _session(response: JSONResponse, token: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_SESSION,
        token,
        max_age=max_age,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )


def apply_result(result: Result) -> JSONResponse:
    response = JSONResponse(status_code=result.status_code, content=result.payload)
    secure = cookie_secure()
    if result.clear_session or result.session_token:
        response.delete_cookie(COOKIE_SESSION, path="/", samesite="lax", secure=secure)
    if result.session_token and result.max_age:
        _session(response, result.session_token, result.max_age)
    if result.csrf_token:
        _csrf(response, result.csrf_token, result.max_age or SESSION_SECONDS)
    return response


def anonymous_csrf(token: str, max_age: int = SESSION_SECONDS) -> JSONResponse:
    response = JSONResponse({"status": "ok"})
    _csrf(response, token, max_age)
    return response


def stamp_csrf(response: JSONResponse, token: str, max_age: int = SESSION_SECONDS) -> None:
    _csrf(response, token, max_age)
