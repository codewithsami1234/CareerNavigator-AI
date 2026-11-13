"""Decide when OCR output is too unreliable to treat as a resume.

A low Tesseract confidence is only one signal. A faint but genuine scan can
score below a perfect page and still contain real wording, so confidence by
itself never rejects a page. Rejection needs low confidence together with a
crowded or noisy page, or with text that does not look like words.
"""
from __future__ import annotations

import re
from typing import Optional

import config

UNREADABLE_MESSAGE = (
    "This image could not be read reliably. The page looks noisy or too unclear "
    "for OCR, and the characters that came back do not form resume text. "
    "Use a clearer, properly oriented photo or scan, with the page upright and well lit, "
    "and try again."
)

BLANK_IMAGE_MESSAGE = (
    "This image did not contain readable text. "
    "Use a clearer, properly oriented photo or scan and try again."
)

_TOKEN_RE = re.compile(r"[A-Za-z]{2,}")
_VOWELS = set("aeiouy")
_COMMON_WORDS = frozenset({
    "the", "and", "with", "for", "from", "that", "this", "your", "have", "has",
    "was", "were", "are", "not", "but", "you", "our", "their", "they", "his",
    "her", "she", "who", "which", "into", "over", "under", "about", "after",
    "before", "between", "using", "used", "built", "build", "worked", "work",
    "working", "experience", "skills", "skill", "education", "university",
    "college", "school", "bachelor", "master", "science", "computer",
    "software", "engineer", "engineering", "developer", "development",
    "project", "projects", "python", "javascript", "typescript", "java",
    "sql", "html", "css", "docker", "github", "email", "phone", "location",
    "summary", "objective", "responsibilities", "designed", "developed",
    "implemented", "managed", "created", "supported", "including", "required",
    "preferred", "qualifications", "years", "team", "data", "analysis",
    "research", "intern", "internship", "company", "labs", "state",
})


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text or "")


def _wordlike(token: str) -> bool:
    """Longer tokens only. Three-letter OCR noise often contains one vowel."""
    if len(token) < 5 or len(token) > 20:
        return False
    vowels = sum(1 for char in token.lower() if char in _VOWELS)
    return vowels >= 2 and vowels / len(token) >= 0.25


def _signals(text: str) -> tuple[float, int]:
    tokens = _tokens(text)
    if not tokens:
        return 1.0, 0
    wordlike = [token for token in tokens if _wordlike(token)]
    ratio = len(wordlike) / len(tokens)
    common = {token.lower() for token in tokens if len(token) >= 3 and token.lower() in _COMMON_WORDS}
    return ratio, len(common)


def unreliable_ocr_reason(
    text: str,
    mean_confidence: Optional[float],
    measured: Optional[dict] = None,
) -> Optional[str]:
    """Return a user-facing reason, or None when the text can still be analyzed.

    Prose-like wording is kept even when confidence is imperfect. Noise is
    rejected only when confidence is low and the page or the tokens agree.
    """
    if mean_confidence is None:
        return None
    tokens = _tokens(text)
    if len(tokens) < 8:
        return None
    ratio, common = _signals(text)
    # Resume wording is kept even when the engine's confidence is poor.
    if common >= config.OCR_UNRELIABLE_MIN_COMMON_WORDS:
        return None
    # Confidence above the low band is not, by itself, a reason to reject.
    if float(mean_confidence) >= config.OCR_UNRELIABLE_MAX_CONFIDENCE:
        return None

    ink = None
    if measured and measured.get("ink_ratio") is not None:
        try:
            ink = float(measured["ink_ratio"])
        except (TypeError, ValueError):
            ink = None
    crowded = ink is not None and ink >= config.CROWDED_INK_RATIO
    gibberish = ratio < config.OCR_GIBBERISH_WORDLIKE_RATIO and common < 3
    if crowded or gibberish:
        return UNREADABLE_MESSAGE
    return None
