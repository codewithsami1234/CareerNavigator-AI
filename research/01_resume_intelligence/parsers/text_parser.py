"""Plain-text resume reader (used for tests and for text pasted by a user)."""
from __future__ import annotations

from pathlib import Path

from schemas import ParseResult, PARSE_OK

_ENCODINGS = ("utf-8-sig", "utf-16", "cp1252", "latin-1")


def decode_bytes(data: bytes) -> str:
    """Decode bytes using a short list of common encodings."""
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")
    for enc in _ENCODINGS:
        if enc == "utf-16":
            continue  # only trusted when a BOM is present (handled above)
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def parse_text_file(path: Path) -> ParseResult:
    result = ParseResult(source_format="text", file_name=path.name)
    try:
        data = path.read_bytes()
    except OSError as exc:
        result.status = "failed"
        result.errors.append(f"Could not read file: {exc.__class__.__name__}: {exc}")
        return result
    if b"\x00" in data[:2048] and not data.startswith((b"\xff\xfe", b"\xfe\xff")):
        result.status = "failed"
        result.errors.append("File contains binary data and does not look like plain text.")
        return result
    result.text = decode_bytes(data)
    result.status = PARSE_OK
    return result
