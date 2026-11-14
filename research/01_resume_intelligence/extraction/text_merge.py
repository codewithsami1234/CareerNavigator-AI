"""Combine native text and OCR text without duplicating the same words.

Overlap is measured with a token Jaccard-style coverage score. It is a
transparent rule, not a semantic match.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Set, Tuple

import config

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")
_HYPHEN_BREAK_RE = re.compile(r"([A-Za-z])-\n([a-z])")


@dataclass
class TextPiece:
    text: str
    method: str
    suppressed_duplicate: bool = False
    confidence: Optional[float] = None


def repair_ocr_text(text: str) -> str:
    """Join a hyphen that Tesseract split across two lines.

    Only a letter, a hyphen, a newline and a lowercase letter are joined, so
    items such as ``AI-ML`` on one line are left alone. Phase 1 ``normalize_text``
    is not changed.
    """
    if not text:
        return ""
    return _HYPHEN_BREAK_RE.sub(r"\1\2", text.replace("\r\n", "\n").replace("\r", "\n"))


def tokens(text: str) -> Set[str]:
    return set(_TOKEN_RE.findall((text or "").lower()))


def coverage(part: Set[str], whole: Set[str]) -> float:
    if not part:
        return 0.0
    return len(part & whole) / len(part)


def combine_native_and_ocr(native: str, ocr_text: str, *, ocr_confidence: Optional[float] = None) -> List[TextPiece]:
    """Return the pieces to keep for one page.

    A suppressed piece is retained for provenance and omitted from the resume
    text. Native text is preferred when the two copies overlap heavily, because
    the text layer is usually cleaner than OCR.
    """
    native = native or ""
    ocr_text = ocr_text or ""
    native_tokens = tokens(native)
    ocr_tokens = tokens(ocr_text)
    if not ocr_text.strip() or not ocr_tokens:
        if native.strip():
            return [TextPiece(native, config.METHOD_NATIVE_PDF, False)]
        return []
    if not native.strip() or not native_tokens:
        return [TextPiece(ocr_text, config.METHOD_OCR, False, ocr_confidence)]

    native_in_ocr = coverage(native_tokens, ocr_tokens)
    ocr_in_native = coverage(ocr_tokens, native_tokens)
    if native_in_ocr >= 0.75 and ocr_in_native >= 0.75:
        return [
            TextPiece(native, config.METHOD_NATIVE_PDF, False),
            TextPiece(ocr_text, config.METHOD_OCR, True, ocr_confidence),
        ]
    if native_in_ocr >= 0.8 and len(ocr_tokens) > len(native_tokens) * 1.4:
        return [
            TextPiece(ocr_text, config.METHOD_OCR, False, ocr_confidence),
            TextPiece(native, config.METHOD_NATIVE_PDF, True),
        ]
    if ocr_in_native >= 0.8 and len(native_tokens) >= len(ocr_tokens):
        return [
            TextPiece(native, config.METHOD_NATIVE_PDF, False),
            TextPiece(ocr_text, config.METHOD_OCR, True, ocr_confidence),
        ]
    return [
        TextPiece(native, config.METHOD_NATIVE_PDF, False),
        TextPiece(ocr_text, config.METHOD_OCR, False, ocr_confidence),
    ]


def included_text(pieces: Sequence[TextPiece]) -> str:
    parts = [piece.text.strip() for piece in pieces if piece.text.strip() and not piece.suppressed_duplicate]
    return "\n\n".join(parts)


def mark_duplicate_pages(page_texts: List[Tuple[int, str]]) -> List[int]:
    """Return page numbers whose text repeats the previous kept page.

    ``page_texts`` is ``(page_number, text)`` in reading order. Short pages are
    never treated as duplicates. The caller decides what to do with the numbers.
    """
    suppressed: List[int] = []
    previous: Optional[Tuple[int, str, Set[str]]] = None
    for number, text in page_texts:
        current = tokens(text)
        if previous is not None and len(previous[2]) >= 12 and len(current) >= 12:
            union = previous[2] | current
            overlap = len(previous[2] & current) / len(union) if union else 0.0
            shorter = min(len(previous[1]), len(text))
            longer = max(len(previous[1]), len(text)) or 1
            if overlap >= 0.92 and shorter / longer >= 0.85:
                suppressed.append(number)
                continue
        previous = (number, text, current)
    return suppressed
