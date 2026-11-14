"""Text normalisation that keeps paragraph boundaries intact."""
from __future__ import annotations

import re
import unicodedata

import config

_BULLET_GLYPHS = "•▪●◦■□►▶➢➤·‣⁃∙○◆◇✓✔"
_ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\u2060\ufeff\u00ad]")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_LEADING_BULLET_RE = re.compile(rf"^[ \t]*[{re.escape(_BULLET_GLYPHS)}][ \t]*")
_LEADING_DASH_BULLET_RE = re.compile(r"^[ \t]*[–—][ \t]+")
_LONE_BULLET_RE = re.compile(rf"^[ \t]*[{re.escape(_BULLET_GLYPHS)}][ \t]*$")


def normalize_text(text: str) -> str:
    """Return a cleaned version of ``text``.

    * Unicode NFKC (ligatures, non-breaking spaces, full-width characters)
    * Removes control / zero-width characters
    * Converts bullet glyphs at line start to ``"- "``
    * Joins a bullet glyph that sits alone on a line with the next line
    * Collapses runs of spaces/tabs and trims every line
    * Collapses runs of blank lines to exactly one blank line
      (so paragraph boundaries survive, but layout noise does not)
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\f", "\n\n")
    text = _ZERO_WIDTH_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = text.replace("\t", " ")

    raw_lines = text.split("\n")

    # Merge bullet glyphs that were extracted on their own line (common in PDFs).
    merged = []
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        if _LONE_BULLET_RE.match(line):
            j = i + 1
            while j < len(raw_lines) and not raw_lines[j].strip():
                j += 1
            if j < len(raw_lines):
                merged.append("- " + raw_lines[j].strip())
                i = j + 1
                continue
            i += 1
            continue
        merged.append(line)
        i += 1

    out = []
    blank_run = 0
    for line in merged:
        line = _LEADING_BULLET_RE.sub("- ", line)
        line = _LEADING_DASH_BULLET_RE.sub("- ", line)
        line = re.sub(r"[ ]{2,}", " ", line).strip()
        if not line:
            blank_run += 1
            if blank_run == 1 and out:
                out.append("")
            continue
        blank_run = 0
        out.append(line)

    while out and not out[-1]:
        out.pop()
    return "\n".join(out)


def count_meaningful_chars(text: str) -> int:
    """Number of letters/digits in ``text`` (whitespace and symbols ignored)."""
    return sum(1 for ch in text if ch.isalnum())


def has_meaningful_text(text: str, minimum: int = config.MIN_MEANINGFUL_CHARS) -> bool:
    return count_meaningful_chars(text) >= minimum
