"""Document parsers and the single entry point ``parse_document``."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import config
from schemas import ParseResult, STATUS_EMPTY, STATUS_FAILED, PARSE_OK
from utils.text_cleaner import has_meaningful_text

from .docx_parser import parse_docx
from .pdf_parser import parse_pdf
from .text_parser import parse_text_file

_FORMAT_BY_EXT = {".pdf": "pdf", ".docx": "docx", ".txt": "text"}


def validate_file(path: Union[str, Path]) -> Tuple[Optional[Path], List[str]]:
    """Check existence, type, extension and size. Returns (path, errors)."""
    try:
        p = Path(path)
    except TypeError:
        return None, ["The file path is not valid."]
    if not p.exists():
        return None, [f"File not found: {p.name or p}"]
    if not p.is_file():
        return None, [f"Not a file: {p.name or p}"]
    ext = p.suffix.lower()
    if ext not in config.SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(config.SUPPORTED_EXTENSIONS))
        return None, [f"Unsupported file type '{ext or '(none)'}'. Supported types: {supported}."]
    try:
        size = p.stat().st_size
    except OSError as exc:
        return None, [f"Could not read file information: {exc.__class__.__name__}"]
    if size == 0:
        return None, ["The file is empty (0 bytes)."]
    if size > config.MAX_FILE_SIZE_BYTES:
        return None, [config.file_too_large_message(size)]
    return p, []


def parse_document(path: Union[str, Path]) -> ParseResult:
    """Validate and parse a PDF / DOCX / TXT file into raw text."""
    p, errors = validate_file(path)
    if p is None:
        name = Path(str(path)).name if path is not None else None
        return ParseResult(status=STATUS_FAILED, file_name=name, errors=errors)

    ext = p.suffix.lower()
    if ext == ".pdf":
        result = parse_pdf(p)
    elif ext == ".docx":
        result = parse_docx(p)
    else:
        result = parse_text_file(p)

    if result.status == PARSE_OK and not has_meaningful_text(result.text):
        result.status = STATUS_EMPTY
        result.warnings.append("The document was read successfully but contains no meaningful text.")
    return result


__all__ = ["parse_document", "validate_file", "parse_pdf", "parse_docx", "parse_text_file"]
