"""Account HTTP routes. Analysis routes stay in api.app."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from accounts.cookies import anonymous_csrf, apply_result, stamp_csrf
from accounts.deps import require_user
from accounts.records import delete_all_records, delete_record, list_records, load_workspace, read_record, save_workspace
from accounts.security import COOKIE_CSRF, COOKIE_SESSION, new_token
from accounts import service

router = APIRouter()


def _ip(request: Request) -> str:
    if request.client is None or not request.client.host:
        return "unknown"
    return request.client.host[:64]


async def _json(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


@router.get("/api/auth/csrf")
def issue_csrf():
    return anonymous_csrf(new_token())


@router.post("/api/auth/register")
async def register(request: Request):
    payload = await _json(request)
    payload.pop("user_id", None)
    return apply_result(service.register(payload))


@router.post("/api/auth/login")
async def login(request: Request):
    payload = await _json(request)
    payload.pop("user_id", None)
    return apply_result(
        service.login(
            payload.get("email"),
            payload.get("password"),
            _ip(request),
            request.cookies.get(COOKIE_SESSION),
        )
    )


@router.post("/api/auth/logout")
def logout(request: Request):
    return apply_result(service.logout(request.cookies.get(COOKIE_SESSION)))


@router.get("/api/auth/session")
def current_session(request: Request):
    principal = service.authenticate_request(request)
    if principal is None:
        response = JSONResponse(status_code=401, content={"user": None})
        if not request.cookies.get(COOKIE_CSRF):
            stamp_csrf(response, new_token())
        return response
    response = JSONResponse({"user": principal.public()})
    if request.cookies.get(COOKIE_CSRF) != principal.csrf_token:
        stamp_csrf(response, principal.csrf_token)
    return response


@router.post("/api/auth/change-password")
async def change_password(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    payload = await _json(request)
    return apply_result(
        service.change_password(principal, payload.get("current_password"), payload.get("password"), payload.get("confirm_password"))
    )


@router.post("/api/auth/profile")
async def profile(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    payload = await _json(request)
    return apply_result(service.update_profile(principal, payload.get("name")))


@router.get("/api/me/workspace")
def get_workspace(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    return {"workspace": load_workspace(principal.id)}


@router.put("/api/me/workspace")
async def put_workspace(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    payload = await _json(request)
    workspace = payload.get("workspace")
    if workspace is None:
        workspace = {}
    if not isinstance(workspace, dict):
        return JSONResponse(status_code=400, content={"status": "failed", "errors": ["The workspace could not be saved."]})
    problem = save_workspace(principal.id, workspace)
    if problem:
        return JSONResponse(status_code=400, content={"status": "failed", "errors": [problem]})
    return {"status": "saved"}


@router.get("/api/records")
def records(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    return list_records(principal.id)


@router.get("/api/records/{record_id}")
def one_record(record_id: str, request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    found = read_record(principal.id, record_id)
    if found is None:
        return JSONResponse(status_code=404, content={"status": "failed", "errors": ["That saved item was not found."]})
    return found


@router.delete("/api/records/{record_id}")
def remove_record(record_id: str, request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    if not delete_record(principal.id, record_id):
        return JSONResponse(status_code=404, content={"status": "failed", "errors": ["That saved item was not found."]})
    return {"status": "deleted"}


@router.delete("/api/records")
def remove_records(request: Request):
    principal = require_user(request)
    if not isinstance(principal, service.Principal):
        return principal
    delete_all_records(principal.id)
    return {"status": "deleted"}
