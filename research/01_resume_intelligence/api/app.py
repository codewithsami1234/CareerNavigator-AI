"""Local endpoints for the React workspace and other clients.

Resume, job, GitHub, and career-report routes call ``web.service`` and return
that object's ``to_dict()``. ``POST /api/report`` builds the same career report
and adds a markdown document plus CSV extracts. It copies the readiness
estimate and does not calculate a second score. ``GET /api/health`` only
reports that this process is up.

Parsing, OCR, matching, scoring, GitHub reading, recommendations, and the
roadmap are unchanged. Request failures use HTTP 400 or 415 and a short
``status: failed`` body because no pipeline object exists yet. Pipeline
results, including ``failed``, stay HTTP 200 so their existing status values
remain in the body. Unexpected exceptions are HTTP 500 and do not include
the exception text.
"""
from __future__ import annotations

import base64
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import config
from accounts.db import prepare_database
from accounts.deps import require_user
from accounts.records import store_record
from accounts.routes import router as account_router
from accounts.security import COOKIE_CSRF, same_secret
from accounts.service import Principal
from api.codec import AnalysisDecodeError, from_dict
from github_analysis.analyze import GitHubAnalysis
from schemas import STATUS_FAILED, JobAnalysis, ResumeAnalysis
from web import service
from web.ui.report_export import comparison_csv, readable_report, report_payload, report_pdf, skills_csv

logger = logging.getLogger("careernavigator.api")


def _mount_workspace(app: FastAPI) -> None:
    """Serve the built React workspace from CAREERNAV_STATIC_DIR when present."""
    raw = os.environ.get("CAREERNAV_STATIC_DIR", "").strip()
    if not raw:
        return
    static_dir = Path(raw).resolve()
    index = static_dir / "index.html"
    if not index.is_file():
        logger.warning("CAREERNAV_STATIC_DIR=%s has no index.html; workspace UI is not mounted", static_dir)
        return
    assets = static_dir / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    async def workspace_root():
        return FileResponse(index)

    @app.get("/{full_path:path}")
    async def workspace_spa(full_path: str):
        if full_path.startswith("api/") or full_path in {"docs", "openapi.json", "redoc"}:
            return JSONResponse(status_code=404, content={"status": STATUS_FAILED, "errors": ["Not found."]})
        candidate = (static_dir / full_path).resolve()
        try:
            candidate.relative_to(static_dir)
        except ValueError:
            return FileResponse(index)
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


def _configure_logging() -> None:
    """Show request lines on stderr. The message text is chosen by the callers."""
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)

_REQUEST_ERRORS = {
    "resume_file": "A resume file is required.",
    "resume_type": "Send the resume as multipart form data.",
    "use_ocr": "use_ocr must be true or false.",
    "job_type": "Send job text as JSON or a job file as multipart form data.",
    "job_text": "Job text must be a string.",
    "job_file": "A job file is required.",
    "json": "The request body is not valid JSON.",
    "username": "username must be a string.",
    "resume_object": "A resume analysis object is required.",
    "analysis_object": "The stored analysis could not be read. Send the object returned by the resume, job, or GitHub endpoint.",
    "weekly_hours": "weekly_hours must be a whole number or be omitted.",
    "unexpected": "The request could not be processed.",
    "label": "must be a string of at most 200 characters.",
}


def _failed(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"status": STATUS_FAILED, "errors": [message]})


def _bool_form(value) -> bool | None:
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if text in {"true", "1", "yes"}:
        return True
    if text in {"false", "0", "no"}:
        return False
    return None


async def _json_object(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _owner(request: Request):
    """The signed-in account, or a response that refuses the request."""
    principal = require_user(request)
    if isinstance(principal, Principal):
        return principal, None
    return None, principal


def create_app() -> FastAPI:
    """Build the app. CORS origins are read when this is called."""
    _configure_logging()
    prepare_database()
    app = FastAPI(title="CareerNavigator AI", docs_url="/docs", redoc_url=None)

    @app.middleware("http")
    async def csrf_guard(request: Request, call_next):
        """Require the CSRF cookie and header to match on changes. Added before CORS so refusals still get CORS headers."""
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            cookie = request.cookies.get(COOKIE_CSRF, "")
            header = request.headers.get("x-csrf-token", "")
            if not same_secret(cookie, header):
                return JSONResponse(
                    status_code=403,
                    content={"status": "failed", "errors": ["Refresh the page and try again."]},
                )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        """Log the route and status only. Bodies, file names, and tokens are not logged."""
        response = await call_next(request)
        logger.info("api method=%s path=%s status=%s", request.method, request.url.path, response.status_code)
        return response

    @app.get("/api/health")
    async def health():
        return {
            "status": "ok",
            "service": "CareerNavigator AI",
            "scoring": "rule-based readiness estimate",
        }

    app.include_router(account_router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.error(
            "api_unhandled method=%s path=%s error=%s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
        )
        return _failed(_REQUEST_ERRORS["unexpected"], 500)

    @app.post("/api/resume")
    async def resume(request: Request):
        owner, denied = _owner(request)
        if denied is not None:
            return denied
        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" not in content_type:
            return _failed(_REQUEST_ERRORS["resume_type"], 415)
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return _failed(_REQUEST_ERRORS["resume_file"], 400)
        use_ocr = _bool_form(form.get("use_ocr"))
        if use_ocr is None:
            return _failed(_REQUEST_ERRORS["use_ocr"], 400)
        data = await upload.read()
        filename = getattr(upload, "filename", "") or ""
        analysis = service.analyze_upload(
            filename,
            data,
            use_ocr=use_ocr,
            content_type=getattr(upload, "content_type", None),
        )
        logger.info(
            "resume_upload bytes=%s suffix=%s ocr=%s status=%s",
            len(data),
            Path(filename).suffix.lower() or "(none)",
            use_ocr,
            analysis.status,
        )
        body = analysis.to_dict()
        store_record(owner.id, "resume", body)
        return JSONResponse(status_code=200, content=body)

    @app.post("/api/job")
    async def job(request: Request):
        owner, denied = _owner(request)
        if denied is not None:
            return denied
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            payload = await _json_object(request)
            if payload is None:
                return _failed(_REQUEST_ERRORS["json"], 400)
            text = payload.get("text", "")
            if not isinstance(text, str):
                return _failed(_REQUEST_ERRORS["job_text"], 400)
            analysis = service.analyze_job_input(text=text)
            logger.info("job_text chars=%s status=%s", len(text), analysis.status)
            body = analysis.to_dict()
            store_record(owner.id, "job", body)
            return JSONResponse(status_code=200, content=body)
        if "multipart/form-data" not in content_type:
            return _failed(_REQUEST_ERRORS["job_type"], 415)
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            return _failed(_REQUEST_ERRORS["job_file"], 400)
        data = await upload.read()
        filename = getattr(upload, "filename", "") or ""
        analysis = service.analyze_job_input(
            filename=filename,
            data=data,
            content_type=getattr(upload, "content_type", None),
        )
        logger.info(
            "job_upload bytes=%s suffix=%s status=%s",
            len(data),
            Path(filename).suffix.lower() or "(none)",
            analysis.status,
        )
        body = analysis.to_dict()
        store_record(owner.id, "job", body)
        return JSONResponse(status_code=200, content=body)

    @app.post("/api/github")
    async def github(request: Request):
        owner, denied = _owner(request)
        if denied is not None:
            return denied
        if not request.headers.get("content-type", "").startswith("application/json"):
            return _failed(_REQUEST_ERRORS["json"], 415)
        payload = await _json_object(request)
        if payload is None:
            return _failed(_REQUEST_ERRORS["json"], 400)
        username = payload.get("username", "")
        if not isinstance(username, str):
            return _failed(_REQUEST_ERRORS["username"], 400)
        analysis = service.read_github_profile(username)
        logger.info("github_lookup status=%s", analysis.status)
        body = analysis.to_dict()
        store_record(owner.id, "github", body)
        return JSONResponse(status_code=200, content=body)

    def _career_inputs(payload: dict):
        if "resume" not in payload or not isinstance(payload.get("resume"), dict):
            return None, _failed(_REQUEST_ERRORS["resume_object"], 400)
        if "job" in payload and payload["job"] is not None and not isinstance(payload["job"], dict):
            return None, _failed(_REQUEST_ERRORS["analysis_object"], 400)
        if "github" in payload and payload["github"] is not None and not isinstance(payload["github"], dict):
            return None, _failed(_REQUEST_ERRORS["analysis_object"], 400)
        try:
            resume_analysis = from_dict(ResumeAnalysis, payload["resume"])
            job = from_dict(JobAnalysis, payload["job"]) if isinstance(payload.get("job"), dict) else None
            github_analysis = (
                from_dict(GitHubAnalysis, payload["github"]) if isinstance(payload.get("github"), dict) else None
            )
        except AnalysisDecodeError:
            return None, _failed(_REQUEST_ERRORS["analysis_object"], 400)
        if "weekly_hours" in payload and payload["weekly_hours"] is not None:
            hours = payload["weekly_hours"]
            if isinstance(hours, bool) or not isinstance(hours, int):
                return None, _failed(_REQUEST_ERRORS["weekly_hours"], 400)
        else:
            hours = None
        return (resume_analysis, job, github_analysis, hours), None

    def _typed_label(payload: dict, key: str):
        if key not in payload or payload[key] is None:
            return "", None
        value = payload[key]
        if not isinstance(value, str) or len(value) > 200:
            return None, _failed(f"{key} {_REQUEST_ERRORS['label']}", 400)
        return value.strip(), None

    @app.post("/api/career-report")
    async def career_report(request: Request):
        owner, denied = _owner(request)
        if denied is not None:
            return denied
        if not request.headers.get("content-type", "").startswith("application/json"):
            return _failed(_REQUEST_ERRORS["json"], 415)
        payload = await _json_object(request)
        if payload is None:
            return _failed(_REQUEST_ERRORS["json"], 400)
        parsed, error = _career_inputs(payload)
        if error is not None:
            return error
        resume_analysis, job, github_analysis, hours = parsed
        report = service.build_career_report(resume_analysis, job, github_analysis, weekly_hours=hours)
        body = report.to_dict()
        store_record(owner.id, "career", body)
        return JSONResponse(status_code=200, content=body)

    @app.post("/api/report")
    async def report(request: Request):
        owner, denied = _owner(request)
        if denied is not None:
            return denied
        """Readable report from objects the other endpoints already returned.

        The readiness number is copied. This route does not score on its own.
        """
        if not request.headers.get("content-type", "").startswith("application/json"):
            return _failed(_REQUEST_ERRORS["json"], 415)
        payload = await _json_object(request)
        if payload is None:
            return _failed(_REQUEST_ERRORS["json"], 400)
        parsed, error = _career_inputs(payload)
        if error is not None:
            return error
        labels = {}
        for key in ("job_title", "company", "target_career"):
            label, label_error = _typed_label(payload, key)
            if label_error is not None:
                return label_error
            labels[key] = label
        resume_analysis, job, github_analysis, hours = parsed
        career = service.build_career_report(resume_analysis, job, github_analysis, weekly_hours=hours)
        document = report_payload(resume_analysis, job, career.comparison, github_analysis, career)
        document["entered_labels"] = {
            "job_title": labels["job_title"] or None,
            "company": labels["company"] or None,
            "target_career": labels["target_career"] or None,
            "note": (
                "These labels were typed by the user. "
                "They were not extracted from the resume or the job description."
            ),
        }
        markdown = readable_report(
            resume_analysis,
            job,
            career.comparison,
            github_analysis,
            career,
            job_title=labels["job_title"],
            company=labels["company"],
            target_career=labels["target_career"],
        )
        pdf_bytes = report_pdf(
            resume_analysis,
            job,
            career.comparison,
            github_analysis,
            career,
            job_title=labels["job_title"],
            company=labels["company"],
            target_career=labels["target_career"],
        )
        body = {
            "status": "success",
            "analysis_status": resume_analysis.status,
            "markdown": markdown,
            "report": document,
            "skills_csv": skills_csv(resume_analysis),
            "comparison_csv": comparison_csv(career.comparison) if career.comparison is not None else None,
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        }
        store_record(owner.id, "report", body)
        return JSONResponse(status_code=200, content=body)

    _mount_workspace(app)
    return app


app = create_app()
