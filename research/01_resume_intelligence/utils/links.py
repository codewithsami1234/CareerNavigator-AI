"""URL detection shared by project extraction and skill evidence.

A *link line* holds only labelled URLs, e.g. ``GitHub: github.com/u/repo`` or
``Live Demo: demo.app  GitHub: github.com/u/repo``. The label names where the
link points. It is not a claim that the person used that platform as a skill.
"""
from __future__ import annotations

import re
from typing import List

URL_RE = re.compile(
    r"(?<![\w@.])(?:https?://\S+|www\.\S+|"
    r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|org|net|io|app|dev|me|pk|edu|co|ai|tech|site|xyz)"
    r"(?:/[^\s|,;]*)?)(?![\w@])",
    re.IGNORECASE)
LINK_LABEL_RE = re.compile(
    r"\b(?:github|gitlab|bitbucket|live demo|demo|website|link|url|repo(?:sitory)?|source(?: code)?|"
    r"portfolio)\s*:\s*",
    re.IGNORECASE)
_BULLET_RE = re.compile(r"^\s*[-*•▪●◦■□►▶➢➤·‣⁃∙○]\s*(?=\S)")


_PROFILE_LABEL_RE = re.compile(
    r"\b(?:linked\s*in|git\s*hub|git\s*lab|bitbucket|leet\s*code|hacker\s*rank|kaggle|stack\s*overflow|"
    r"medium|portfolio|website|twitter|x\s*\(\s*twitter\s*\)|x)\b",
    re.IGNORECASE)


def is_profile_label_line(line: str) -> bool:
    """True for a header row such as ``LinkedIn | GitHub | LeetCode | X (Twitter)``.

    Requires at least two labels and nothing else except separators, so a
    tagline like ``GitHub Actions enthusiast`` does not qualify.
    """
    s = _BULLET_RE.sub("", line).strip()
    labels = _PROFILE_LABEL_RE.findall(s)
    if len(labels) < 2:
        return False
    rest = _PROFILE_LABEL_RE.sub(" ", s)
    return not rest.strip(" \t|•·,;/-–—:()")


def urls(text: str) -> List[str]:
    return [m.group(0).rstrip(".,;)") for m in URL_RE.finditer(text)]


def is_link_line(line: str) -> bool:
    """True when ``line`` is only link labels, URLs and separators."""
    s = _BULLET_RE.sub("", line).strip()
    if not s or not urls(s):
        return False
    rest = URL_RE.sub(" ", s)
    rest = LINK_LABEL_RE.sub(" ", rest + " ")
    return not rest.strip(" \t|•·-–—:")
