"""Configurable resume-section detection.

A heading is a short line whose normalised text equals one of the aliases in
``data/section_aliases.json``. Text before the first heading is returned as a
``header`` section (usually name + contact details). Nothing is dropped: every
line of the cleaned text belongs to exactly one section.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import config
from schemas import Section

# Lines that start with a list marker are bullets, never headings.
_BULLET_START_RE = re.compile(r"^\s*(?:[-*]\s+|[•▪●◦■□►▶➢➤·‣⁃∙○]\s*)\S")
_LEAD_DECOR_RE = re.compile(r"^[\s#>*_=\-~|•·\[\(]+")
_TRAIL_DECOR_RE = re.compile(r"[\s#*_=\-~|•·\]\):.]+$")
_LEAD_NUMBER_RE = re.compile(r"^(?:\d{1,2}|[ivx]{1,4})[.)]\s+", re.IGNORECASE)
_INLINE_RE = re.compile(r"^(?P<h>[^:]{2,40}):\s*(?P<rest>\S.*)$")
_TRAIL_PAREN_RE = re.compile(r"\s*\([^()]*\)\s*$")
# Grouped headings such as "AI / ML PROJECTS" or "WEB PROJECTS". Only all-caps
# lines qualify, so a sentence like "Completed several projects" is not a heading.
_GROUP_SUFFIX_SECTIONS = {"projects": "projects", "project": "projects"}
_MAX_GROUP_QUALIFIER_WORDS = 4


def _grouped_heading(raw: str) -> Optional[str]:
    letters = [ch for ch in raw if ch.isalpha()]
    if len(letters) < 6 or raw != raw.upper():
        return None
    words = normalize_heading(_TRAIL_PAREN_RE.sub("", raw)).replace("/", " ").split()
    if len(words) < 2 or len(words) > _MAX_GROUP_QUALIFIER_WORDS + 1:
        return None
    return _GROUP_SUFFIX_SECTIONS.get(words[-1])


def _is_single_letter(token: str) -> bool:
    return len(token) == 1 and token.isalpha()


def _collapse_letter_spacing(text: str) -> str:
    """Join letter-spaced fragments such as ``Decl a r a tion``.

    A single letter continues the current word. A short tail such as ``tion``
    continues that word only after two or more single letters were already
    absorbed into a longer fragment. Separate words stay separate, so a normal
    sentence is not folded into one token.
    """
    tokens = [token for token in text.split(" ") if token]
    if not any(_is_single_letter(token) for token in tokens):
        return text

    groups: List[str] = []
    buf: List[str] = []
    long_in_group = False
    singles_in_group = 0
    prev_single = False

    def close() -> None:
        nonlocal buf, long_in_group, singles_in_group, prev_single
        if buf:
            groups.append("".join(buf))
        buf = []
        long_in_group = False
        singles_in_group = 0
        prev_single = False

    for token in tokens:
        single = _is_single_letter(token)
        if not buf:
            buf = [token]
            long_in_group = len(token) >= 2
            singles_in_group = 1 if single else 0
            prev_single = single
            continue
        if single:
            buf.append(token)
            singles_in_group += 1
            prev_single = True
            continue
        if prev_single and long_in_group and singles_in_group >= 2 and len(token) <= 5:
            buf.append(token)
            long_in_group = True
            prev_single = False
            continue
        close()
        buf = [token]
        long_in_group = len(token) >= 2
        singles_in_group = 1 if single else 0
        prev_single = False
    close()
    return " ".join(groups)


def normalize_heading(raw: str) -> str:
    """Lower-case a heading and strip decoration so it can be compared to aliases.

    Fully spaced letters (``S K I L L S``) and broken words (``Decl a r a tion``)
    collapse before the alias lookup. Ordinary multi-word lines are left as words.
    """
    s = _LEAD_DECOR_RE.sub("", raw.strip())
    s = _LEAD_NUMBER_RE.sub("", s)
    s = _TRAIL_DECOR_RE.sub("", s)
    tokens = s.split(" ")
    if len(tokens) >= 3 and all(len(t) == 1 for t in tokens):   # "S K I L L S"
        s = "".join(tokens)
    else:
        s = _collapse_letter_spacing(s)
    s = s.lower().replace("&", " and ")
    return re.sub(r"\s+", " ", s).strip()


def load_section_aliases(path: Union[str, Path, None] = None) -> Dict[str, List[str]]:
    path = Path(path) if path else config.SECTION_ALIASES_PATH
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    aliases = {k: v for k, v in data.items() if not k.startswith("_")}
    for name, values in aliases.items():
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(f"Section '{name}' in {path.name} must be a list of strings.")
    return aliases


class SectionExtractor:
    def __init__(self, aliases: Optional[Dict[str, List[str]]] = None):
        aliases = aliases if aliases is not None else load_section_aliases()
        self._alias_map: Dict[str, str] = {}
        for name, values in aliases.items():
            for value in values:
                self._alias_map[normalize_heading(value)] = name

    # ---- heading detection -------------------------------------------------
    def detect_heading(self, line: str) -> Optional[Tuple[str, str, Optional[str]]]:
        """Return (section_name, heading_text, inline_content) or None."""
        raw = line.strip()
        if not raw or len(raw) > config.MAX_HEADING_CHARS or _BULLET_START_RE.match(raw):
            return None

        norm = normalize_heading(raw)
        if norm and len(norm.split()) <= config.MAX_HEADING_WORDS:
            if norm in self._alias_map:
                return self._alias_map[norm], raw, None
            # Compound headings such as "Education & Qualifications" or "Skills / Tools".
            parts = [p for p in re.split(r"\s+and\s+|\s*/\s*|\s*,\s*", norm) if p]
            if len(parts) > 1 and all(p in self._alias_map for p in parts):
                return self._alias_map[parts[0]], raw, None
        grouped = _grouped_heading(raw)
        if grouped and grouped in self._alias_map.values():
            return grouped, raw, None

        m = _INLINE_RE.match(raw)
        if m:
            name = self._alias_map.get(normalize_heading(m.group("h")))
            if name in config.INLINE_HEADING_SECTIONS:
                return name, m.group("h").strip(), m.group("rest").strip()
        return None

    # ---- main entry --------------------------------------------------------
    def extract(self, text: str) -> List[Section]:
        lines = text.split("\n") if text else []
        sections: List[Section] = []

        cur_name, cur_heading, cur_start = "header", None, 0
        cur_lines: List[str] = []

        def close(end_index: int) -> None:
            content = "\n".join(cur_lines).strip("\n")
            if cur_name == "header" and not content.strip():
                return
            sections.append(Section(
                name=cur_name, heading=cur_heading, start_line=cur_start,
                end_line=max(end_index, cur_start), content=content,
            ))

        for i, line in enumerate(lines):
            hit = self.detect_heading(line)
            # An inline label that repeats the current section ("Programming Languages: ..."
            # inside Skills) is ordinary content, not a new section. Likewise "Languages: Java, Go"
            # inside a Skills section is a sub-label for programming languages, not spoken languages.
            if hit and hit[2] is not None and (
                    hit[0] == cur_name or (cur_name == "skills" and hit[0] == "languages")):
                hit = None
            if hit:
                close(i - 1)
                cur_name, cur_heading, cur_start = hit[0], hit[1], i
                cur_lines = [hit[2]] if hit[2] else []
            else:
                cur_lines.append(line)
        close(len(lines) - 1)
        return sections


def section_text(sections: List[Section], name: str) -> str:
    """Join the content of every section called ``name`` (headings may repeat)."""
    return "\n\n".join(s.content for s in sections if s.name == name and s.content.strip())


def section_names(sections: List[Section]) -> List[str]:
    return [s.name for s in sections]
