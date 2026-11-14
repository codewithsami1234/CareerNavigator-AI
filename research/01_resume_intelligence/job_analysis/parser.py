"""Read a job description from pasted text or a PDF, DOCX, or TXT file.

Section headings come from ``data/job_section_aliases.json``. The resume
heading list is not used, so a resume section name does not change a job
posting's priority. This module does not extract requirements.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Union

import config
from extractors.section_extractor import SectionExtractor, load_section_aliases, normalize_heading
from parsers import parse_document
from schemas import PARSE_OK, JobAnalysis, STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR
from utils.text_cleaner import count_meaningful_chars, normalize_text

# A posting can be a short bullet list. The resume gate (50 letters) would
# drop those, so job text uses its own floor. Symbol-only input stays empty.
_MIN_JOB_CHARS = 8
_EXTENSIONS = {".pdf", ".docx", ".txt"}
_EMPTY_REASON = "No meaningful text was found, so no requirements could be extracted."
_NO_HEADING_WARNING = (
    "No job-description headings were recognised. Priorities stay unspecified "
    "unless a line explicitly says required or preferred."
)
_INLINE_RE = re.compile(r"^(?P<h>[^:]{2,70}):\s*(?P<rest>\S.*)$")


@lru_cache(maxsize=1)
def job_section_extractor() -> SectionExtractor:
    return SectionExtractor(load_section_aliases(config.JOB_SECTION_ALIASES_PATH))


def _as_path(value: Union[str, Path, None]) -> Optional[Path]:
    """Return a path only when the value looks like a file, not pasted text."""
    if isinstance(value, Path):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or "\n" in value or "\r" in value or len(stripped) > 240:
        return None
    candidate = Path(stripped)
    if candidate.suffix.lower() not in _EXTENSIONS:
        return None
    if candidate.exists() or "/" in stripped or "\\" in stripped:
        return candidate
    return None


def _split_inline_headings(text: str) -> str:
    """Turn ``Requirements: Python`` into a heading line plus a content line.

    The resume section extractor only keeps inline text for a few resume
    sections. Job headings are split here so that rule stays unchanged.
    """
    aliases = job_section_extractor()._alias_map
    lines: List[str] = []
    for line in text.split("\n"):
        match = _INLINE_RE.match(line.strip())
        if match and normalize_heading(match.group("h")) in aliases:
            lines.append(match.group("h").strip())
            lines.append(match.group("rest").strip())
        else:
            lines.append(line)
    return "\n".join(lines)


def _failed(reason: str, *, source_format: str = "unknown", file_name: Optional[str] = None,
            errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None) -> JobAnalysis:
    return JobAnalysis(
        status=STATUS_FAILED, source_format=source_format, file_name=file_name,
        warnings=list(warnings or []), errors=list(errors or [reason]), reason=reason,
    )


def _from_text(text: str, *, source_format: str, file_name: Optional[str],
               warnings: Optional[List[str]] = None) -> JobAnalysis:
    clean = normalize_text(text)
    result = JobAnalysis(
        source_format=source_format, file_name=file_name, text_length=len(clean),
        warnings=list(warnings or []),
    )
    if count_meaningful_chars(clean) < _MIN_JOB_CHARS:
        result.status = STATUS_EMPTY
        result.reason = _EMPTY_REASON
        result.warnings.append(_EMPTY_REASON)
        return result

    sections = job_section_extractor().extract(_split_inline_headings(clean))
    result.sections = sections
    if not ({section.name for section in sections} - {"header"}):
        result.warnings.append(_NO_HEADING_WARNING)
    # Requirements extraction decides success versus partial.
    result.status = PARSE_OK
    return result


def prepare_job(text_or_path: Union[str, Path, None]) -> JobAnalysis:
    """Load text and sections. ``status`` is ``ok`` when extraction can continue.

    Empty, unreadable, and image-only files stop here with a reason. They do
    not produce an empty requirement list that looks like a successful read.
    """
    path = _as_path(text_or_path)
    if path is not None:
        return _from_file(path)
    if not isinstance(text_or_path, str):
        return _failed("analyze_job expects pasted text or a PDF, DOCX, or TXT path.")
    return _from_text(text_or_path, source_format="text", file_name=None)


def _from_file(path: Path) -> JobAnalysis:
    try:
        parsed = parse_document(path)
    except Exception as exc:
        return _failed(f"Unexpected error while reading the file: {exc.__class__.__name__}: {exc}")

    if parsed.status == STATUS_FAILED:
        reason = parsed.errors[0] if parsed.errors else "The file could not be read."
        return _failed(
            reason, source_format=parsed.source_format, file_name=parsed.file_name,
            errors=parsed.errors, warnings=parsed.warnings,
        )
    if parsed.status == STATUS_NEEDS_OCR:
        reason = "The file does not contain enough extractable text to read as a job description."
        return JobAnalysis(
            status=STATUS_NEEDS_OCR, source_format=parsed.source_format, file_name=parsed.file_name,
            warnings=list(parsed.warnings), errors=list(parsed.errors), reason=reason,
        )
    usable = count_meaningful_chars(parsed.text or "")
    if parsed.status == STATUS_EMPTY and usable < _MIN_JOB_CHARS:
        reason = parsed.warnings[-1] if parsed.warnings else _EMPTY_REASON
        return JobAnalysis(
            status=STATUS_EMPTY, source_format=parsed.source_format, file_name=parsed.file_name,
            warnings=list(parsed.warnings) or [_EMPTY_REASON], errors=list(parsed.errors),
            reason=reason,
        )

    # A short file can be marked empty by the resume-length gate. Job bullets
    # are still readable, so keep going when enough letters are present.
    prior_warnings = list(parsed.warnings) if parsed.status == PARSE_OK else []
    return _from_text(
        parsed.text or "", source_format=parsed.source_format, file_name=parsed.file_name,
        warnings=prior_warnings,
    )
