"""Taxonomy-driven skill extraction with evidence.

Matching rules
--------------
* ``aliases`` (and the canonical name) match case-insensitively on word boundaries.
* ``case_sensitive_aliases`` match exactly as written (e.g. ``AI``).
* ``context_aliases`` (e.g. ``py``) match only if a ``context_cues`` word appears on the
  same or an adjacent line of the same section.
* ``name_requires_context`` skills (``Go``, ``R``, ``C`` ...) match case-sensitively only
  with a cue nearby, or as a list item inside a *Skills* section.
* E-mail addresses and URLs are masked before matching.
* Link lines (``GitHub: github.com/u/repo``) are not evidence: the label says where the
  link points, not that the platform was used as a skill.
* When two matches overlap, the longer one wins (``Java Script`` -> JavaScript, not Java).

Evidence: each skill keeps the section and line where it was found. A skill found in
Experience/Projects is ``used``; anywhere else it is only ``mentioned``. Proficiency is
never inferred.
"""
from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import config
from schemas import DetectedSkill, Section, SkillEvidence
from utils.links import is_link_line, is_profile_label_line

_PREFIX = r"(?<![A-Za-z0-9_])(?<![A-Za-z0-9_]\.)"
_SUFFIX = r"(?![A-Za-z0-9_])"

_MASK_RE = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"                         # e-mail
    r"|(?:https?://|www\.)\S+"                              # URL
    r"|\b[\w-]+\.(?:com|org|dev|pk|edu|co)(?:/\S*)?",    # bare domain
    re.IGNORECASE,
)
_CONTACT_LINE_RE = re.compile(
    r"[\w.+-]+@[\w-]+\.\w+|https?://|www\.|\b[\w-]+\.(?:com|org|dev|pk|edu|co)\b|\+?\d[\d\s().-]{8,}\d",
    re.IGNORECASE,
)


def mask_contact_tokens(line: str) -> str:
    """Blank out e-mails/URLs (keeping string length) so they cannot match skills."""
    return _MASK_RE.sub(lambda m: " " * len(m.group()), line)


def _alias_regex(alias: str, ignorecase: bool) -> "re.Pattern[str]":
    parts = re.split(r"([\s\-]+)", alias.strip())
    pieces = []
    for part in parts:
        if not part:
            continue
        if re.fullmatch(r"[\s\-]+", part):
            pieces.append(r"[\s\-]+" if re.search(r"\s", part) else r"[\s\-]?")
        else:
            pieces.append(re.escape(part))
    body = "".join(pieces)
    suffix = _SUFFIX if alias[-1] in "+#" else _SUFFIX + r"(?![+#])"
    return re.compile(_PREFIX + body + suffix, re.IGNORECASE if ignorecase else 0)


def _cue_regex(cues: List[str]) -> Optional["re.Pattern[str]"]:
    if not cues:
        return None
    body = "|".join(re.escape(c) for c in sorted(set(cues), key=len, reverse=True))
    return re.compile(r"(?<![A-Za-z0-9_])(?:" + body + r")(?![A-Za-z0-9_])", re.IGNORECASE)


# ---- taxonomy loading / validation -----------------------------------------
def validate_taxonomy(data: dict) -> List[str]:
    """Return a list of problems found in a taxonomy dict (empty list = valid)."""
    problems: List[str] = []
    cats = data.get("categories")
    if not isinstance(cats, dict) or not cats:
        return ["Taxonomy needs a non-empty 'categories' object."]
    seen_names: Dict[str, str] = {}
    seen_aliases: Dict[Tuple[str, bool], str] = {}
    for cat, skills in cats.items():
        if not isinstance(skills, list):
            problems.append(f"Category '{cat}' must be a list.")
            continue
        for s in skills:
            name = s.get("name") if isinstance(s, dict) else None
            if not name or not isinstance(name, str):
                problems.append(f"A skill in '{cat}' has no 'name'.")
                continue
            if name.lower() in seen_names:
                problems.append(f"Duplicate skill name '{name}' (also in '{seen_names[name.lower()]}').")
            seen_names[name.lower()] = cat
            for key in ("aliases", "case_sensitive_aliases", "context_aliases", "context_cues",
                        "previous_categories"):
                if key in s and not (isinstance(s[key], list) and all(isinstance(x, str) for x in s[key])):
                    problems.append(f"'{name}': '{key}' must be a list of strings.")
            if (s.get("context_aliases") or s.get("name_requires_context")) and not s.get("context_cues") \
                    and not s.get("name_requires_context"):
                problems.append(f"'{name}': context_aliases need context_cues.")
            forms = [(a.lower(), False) for a in [name] + s.get("aliases", [])
                     if not (a == name and s.get("name_requires_context"))]
            forms += [(a, True) for a in s.get("case_sensitive_aliases", []) + s.get("context_aliases", [])]
            for form in forms:
                if form in seen_aliases and seen_aliases[form] != name:
                    problems.append(f"Alias '{form[0]}' is used by both '{seen_aliases[form]}' and '{name}'.")
                seen_aliases[form] = name
    return problems


def load_taxonomy(path: Union[str, Path, None] = None) -> dict:
    path = Path(path) if path else config.SKILLS_TAXONOMY_PATH
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    problems = validate_taxonomy(data)
    if problems:
        raise ValueError("Invalid skills taxonomy:\n- " + "\n- ".join(problems))
    return data


class _Pattern:
    __slots__ = ("skill", "regex", "kind", "alias")

    def __init__(self, skill: str, regex, kind: str, alias: str):
        self.skill, self.regex, self.kind, self.alias = skill, regex, kind, alias


class SkillExtractor:
    def __init__(self, taxonomy_path: Union[str, Path, None] = None, taxonomy: Optional[dict] = None):
        data = taxonomy if taxonomy is not None else load_taxonomy(taxonomy_path)
        if taxonomy is not None:
            problems = validate_taxonomy(data)
            if problems:
                raise ValueError("Invalid skills taxonomy:\n- " + "\n- ".join(problems))
        self.categories: Dict[str, str] = {}      # skill -> category
        self.previous_categories: Dict[str, List[str]] = {}   # skill -> categories in older taxonomies
        self._category_order: List[str] = list(data["categories"].keys())
        self._cues: Dict[str, Optional["re.Pattern[str]"]] = {}
        self._patterns: List[_Pattern] = []

        for cat, skills in data["categories"].items():
            for s in skills:
                name = s["name"]
                self.categories[name] = cat
                if s.get("previous_categories"):
                    self.previous_categories[name] = list(s["previous_categories"])
                self._cues[name] = _cue_regex(s.get("context_cues", []))
                plain = ([] if s.get("name_requires_context") else [name]) + s.get("aliases", [])
                for alias in plain:
                    self._patterns.append(_Pattern(name, _alias_regex(alias, True), "plain", alias))
                for alias in s.get("case_sensitive_aliases", []):
                    self._patterns.append(_Pattern(name, _alias_regex(alias, False), "plain", alias))
                for alias in s.get("context_aliases", []):
                    self._patterns.append(_Pattern(name, _alias_regex(alias, False), "context_alias", alias))
                if s.get("name_requires_context"):
                    self._patterns.append(_Pattern(name, _alias_regex(name, False), "context_name", name))

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _is_list_item(line: str, start: int, end: int) -> bool:
        before = line[:start].rstrip()
        after = line[end:].lstrip()
        ok_before = (not before) or before[-1] in ",;|/:(&" or before.lower().endswith(" and") \
            or before.lower() == "and"
        ok_after = (not after) or after[0] in ",;|/)&." or after.lower().startswith("and ")
        return ok_before and ok_after

    def _match_line(self, masked: List[str], i: int, section_name: str) -> Dict[str, str]:
        """Return {skill_name: matched_text} for line ``i`` of a section."""
        line = masked[i]
        window = "\n".join(masked[max(0, i - 1): i + 2])
        hits: List[Tuple[int, int, str, str]] = []
        for pat in self._patterns:
            for m in pat.regex.finditer(line):
                if pat.kind == "plain":
                    ok = True
                else:
                    cue = self._cues.get(pat.skill)
                    ok = bool(cue and cue.search(window))
                    if not ok and pat.kind == "context_name" and section_name == "skills":
                        ok = self._is_list_item(line, m.start(), m.end())
                if ok:
                    hits.append((m.start(), m.end(), pat.skill, m.group()))
                    break   # one hit per pattern per line is enough
        # Overlap resolution: drop matches strictly contained in a longer match of another skill.
        kept: Dict[str, str] = OrderedDict()
        for s0, e0, skill, text in hits:
            contained = any(
                (s1 <= s0 and e0 <= e1 and (e1 - s1) > (e0 - s0)) and other != skill
                for s1, e1, other, _ in hits
            )
            if not contained and skill not in kept:
                kept[skill] = text
        return kept

    # ---- public API --------------------------------------------------------
    def extract(self, sections: List[Section]) -> List[DetectedSkill]:
        found: "OrderedDict[str, dict]" = OrderedDict()
        for sec in sections:
            if sec.name in config.SKILL_SCAN_EXCLUDED_SECTIONS:
                continue
            raw_lines = sec.content.split("\n")
            masked = [mask_contact_tokens(l) for l in raw_lines]
            ev_type = "used" if sec.name in config.USED_EVIDENCE_SECTIONS else "mentioned"
            for i, raw in enumerate(raw_lines):
                if not raw.strip():
                    continue
                if sec.name == "header" and _CONTACT_LINE_RE.search(raw):
                    continue
                if is_link_line(raw) or (sec.name == "header" and is_profile_label_line(raw)):
                    continue
                for skill, matched in self._match_line(masked, i, sec.name).items():
                    rec = found.setdefault(skill, {"lines": set(), "matched": [], "evidence": []})
                    key = (sec.name, raw.strip())
                    if key in rec["lines"]:
                        continue
                    rec["lines"].add(key)
                    if matched not in rec["matched"]:
                        rec["matched"].append(matched)
                    text = raw.strip()
                    if len(text) > config.EVIDENCE_TEXT_MAX_CHARS:
                        text = text[: config.EVIDENCE_TEXT_MAX_CHARS - 3] + "..."
                    rec["evidence"].append(SkillEvidence(
                        section=sec.name, text=text, evidence_type=ev_type, matched_as=matched))

        results: List[DetectedSkill] = []
        for skill, rec in found.items():
            evidence = sorted(rec["evidence"], key=lambda e: 0 if e.evidence_type == "used" else 1)
            overall = "used" if any(e.evidence_type == "used" for e in evidence) else "mentioned"
            results.append(DetectedSkill(
                name=skill, category=self.categories[skill], evidence_type=overall,
                mention_count=len(rec["lines"]), matched_as=rec["matched"],
                evidence=evidence[: config.MAX_EVIDENCE_PER_SKILL],
            ))
        order = {c: i for i, c in enumerate(self._category_order)}
        results.sort(key=lambda s: (order.get(s.category, 99), s.name.lower()))
        return results

    def find_in_text(self, text: str, section_name: str = "unsectioned") -> List[str]:
        """Names of taxonomy skills found in a free-text block (used for per-project tech)."""
        sec = Section(name=section_name, heading=None, start_line=0, end_line=0, content=text)
        return [s.name for s in self.extract([sec])]
