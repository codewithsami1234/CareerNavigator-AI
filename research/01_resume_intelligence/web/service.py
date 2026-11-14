"""Validate an upload and call the existing resume pipeline.

TXT and DOCX always use Phase 1 ``analyze_resume``. A PDF uses Phase 1 unless
the caller asks for OCR, in which case Phase 2 ``analyze_document`` reads
native text and OCRs sparse pages. PNG and JPEG always use Phase 2. With OCR
off, an image returns ``needs_ocr`` and is not read. This module does not log
file contents and does not keep the upload after the call returns.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import config
from pipeline import analyze_document, analyze_job, analyze_resume, compare
from schemas import JobAnalysis, MatchReport, ResumeAnalysis, STATUS_FAILED
from vision.image_io import sniff_image_format

# Job uploads stay on PDF, DOCX, and TXT. Resume uploads also accept a
# photographed PNG or JPEG, which the Phase 2 reader OCRs when asked.
SUPPORTED_EXTENSIONS = config.SUPPORTED_EXTENSIONS
RESUME_EXTENSIONS = config.PHASE2_EXTENSIONS

_MIME_BY_SUFFIX = {
    ".pdf": frozenset({"application/pdf"}),
    ".docx": frozenset({
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    }),
    ".txt": frozenset({"text/plain", "text/txt"}),
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg", "image/jpg"}),
    ".jpeg": frozenset({"image/jpeg", "image/jpg"}),
}


def safe_filename(filename: str) -> str:
    """Keep only the base name so a path in the upload name cannot escape."""
    name = Path(str(filename or "")).name.strip()
    cleaned = "".join(ch for ch in name if ch.isprintable() and ch not in '\\/:*?"<>|')
    cleaned = cleaned.strip(" .")
    if cleaned in {"", ".", ".."}:
        return "upload"
    return cleaned


def content_error(suffix: str, data: bytes) -> str | None:
    """Reject bytes that do not match the extension. The message contains no file contents."""
    if suffix == ".pdf":
        if b"%PDF-" not in data[:1024]:
            return "The file extension is .pdf, but the contents are not a PDF."
    elif suffix == ".docx":
        if not data.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")):
            return "The file extension is .docx, but the contents are not a Word document."
    elif suffix in config.IMAGE_EXTENSIONS:
        expected = "png" if suffix == ".png" else "jpeg"
        if sniff_image_format(data) != expected:
            return "The file is not a valid PNG or JPEG image (the contents do not match the extension)."
    elif suffix == ".txt":
        if data.startswith((b"%PDF-", b"PK\x03\x04", b"MZ", b"\x89PNG", b"\xff\xd8\xff")) or sniff_image_format(data):
            return "The file extension is .txt, but the contents are not plain text."
        if b"\x00" in data[:8192]:
            return "The file extension is .txt, but the contents look binary."
    return None


def mime_error(suffix: str, content_type: str | None) -> str | None:
    """Reject a declared content type that disagrees with the extension.

    An empty type and ``application/octet-stream`` are allowed. Browsers use
    both for valid DOCX and image files. The supplied type is not copied into
    the message.
    """
    if not content_type:
        return None
    media = content_type.split(";", 1)[0].strip().lower()
    if media in {"", "application/octet-stream"}:
        return None
    allowed = _MIME_BY_SUFFIX.get(suffix)
    if not allowed or media in allowed:
        return None
    return "The uploaded content type does not match the file extension."


def _failed_resume(name: str, message: str) -> ResumeAnalysis:
    return ResumeAnalysis(status=STATUS_FAILED, file_name=name, errors=[message])


def analyze_upload(
    filename: str,
    data: bytes,
    *,
    use_ocr: bool = False,
    content_type: str | None = None,
) -> ResumeAnalysis:
    """Read ``data`` with the pipeline. Bad files return a failed analysis."""
    safe = safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in RESUME_EXTENSIONS:
        shown = suffix or "(none)"
        allowed = ", ".join(sorted(RESUME_EXTENSIONS))
        return _failed_resume(safe, f"Unsupported file type '{shown}'. Supported types: {allowed}.")
    payload = data or b""
    if len(payload) == 0:
        return _failed_resume(safe, "The file is empty (0 bytes).")
    if len(payload) > config.MAX_FILE_SIZE_BYTES:
        return _failed_resume(safe, config.file_too_large_message(len(payload)))
    mismatch = content_error(suffix, payload)
    if mismatch:
        return _failed_resume(safe, mismatch)
    typed = mime_error(suffix, content_type)
    if typed:
        return _failed_resume(safe, typed)

    directory = tempfile.mkdtemp(prefix="cn-upload-")
    try:
        path = Path(directory) / safe
        path.write_bytes(payload)
        try:
            if suffix in config.IMAGE_EXTENSIONS:
                return analyze_document(path, ocr=use_ocr)
            if suffix == ".pdf" and use_ocr:
                return analyze_document(path, ocr=True)
            return analyze_resume(path)
        except Exception as exc:
            return _failed_resume(safe, f"The file could not be processed ({exc.__class__.__name__}).")
    finally:
        shutil.rmtree(directory, ignore_errors=True)


def _reject_job_upload(
    filename: str,
    data: bytes,
    content_type: str | None = None,
) -> tuple[str, JobAnalysis | None]:
    """Return ``(safe_name, failed_analysis)``. The analysis is None when the bytes can be read."""
    safe = safe_filename(filename)
    suffix = Path(safe).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        shown = suffix or "(none)"
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        message = f"Unsupported file type '{shown}'. Supported types: {allowed}."
        return safe, JobAnalysis(status=STATUS_FAILED, file_name=safe, reason=message, errors=[message])
    payload = data or b""
    if len(payload) == 0:
        reason = "The file is empty (0 bytes)."
        return safe, JobAnalysis(status=STATUS_FAILED, file_name=safe, reason=reason, errors=[reason])
    if len(payload) > config.MAX_FILE_SIZE_BYTES:
        reason = config.file_too_large_message(len(payload))
        return safe, JobAnalysis(status=STATUS_FAILED, file_name=safe, reason=reason, errors=[reason])
    mismatch = content_error(suffix, payload) or mime_error(suffix, content_type)
    if mismatch:
        return safe, JobAnalysis(status=STATUS_FAILED, file_name=safe, reason=mismatch, errors=[mismatch])
    return safe, None


def analyze_job_input(
    text: str = "",
    filename: str | None = None,
    data: bytes | None = None,
    content_type: str | None = None,
) -> JobAnalysis:
    """Read pasted text, or a temporary PDF, DOCX, or TXT upload.

    A file is used when ``filename`` or ``data`` is provided. Pasted text is
    used otherwise. The upload is deleted even if reading raises. OCR is not run.
    """
    if filename is not None or data is not None:
        safe, rejected = _reject_job_upload(filename or "", data or b"", content_type)
        if rejected is not None:
            return rejected
        directory = tempfile.mkdtemp(prefix="cn-upload-")
        try:
            path = Path(directory) / safe
            path.write_bytes(data or b"")
            try:
                return analyze_job(path)
            except Exception as exc:
                reason = f"The file could not be processed ({exc.__class__.__name__})."
                return JobAnalysis(status=STATUS_FAILED, file_name=safe, reason=reason, errors=[reason])
        finally:
            shutil.rmtree(directory, ignore_errors=True)
    if not isinstance(text, str):
        reason = "analyze_job expects pasted text or a PDF, DOCX, or TXT path."
        return JobAnalysis(status=STATUS_FAILED, reason=reason, errors=[reason])
    return analyze_job(text)


def compare_with_resume(resume: ResumeAnalysis, job: JobAnalysis) -> MatchReport:
    """Compare a resume analysis with a job analysis. No score is added."""
    return compare(resume, job)


def read_github_profile(username_or_url: str):
    """Read a public GitHub profile. The resume is not sent.

    This calls ``https://api.github.com`` unless the username is rejected
    locally. No token is required. ``GITHUB_TOKEN`` is used only when that
    environment variable is already set, and it is not returned.
    """
    from pipeline import analyze_github

    return analyze_github(username_or_url if isinstance(username_or_url, str) else "")


def build_career_report(resume, job=None, github=None, weekly_hours=None):
    """Build readiness, recommendations, and a roadmap from stored results.

    This does not read a file and does not call GitHub. ``weekly_hours`` is
    omitted unless it is a positive integer.
    """
    from pipeline import career_report

    hours = weekly_hours if isinstance(weekly_hours, int) and not isinstance(weekly_hours, bool) and weekly_hours > 0 else None
    return career_report(resume, job, github, weekly_hours=hours)
