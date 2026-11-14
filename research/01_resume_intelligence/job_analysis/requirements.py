"""Turn job-description sections into required, preferred, or unspecified items.

Priority comes from the heading and from explicit words on the same line.
When those disagree, or when the line says both required and preferred, the
priority is unspecified. Nothing is promoted to required by default.

Skills use the resume taxonomy and the same alias rules. A longer stated
phrase such as "React hooks" stays its own requirement and does not collapse
into the shorter taxonomy skill inside it. Degree, certification, and years
are recorded only when the line states them. Years that name a skill stay
separate from that skill. Benefits, company descriptions, and other
promotional sections are not requirements.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from extractors.entity_extractor import _find_degree
from extractors.skill_extractor import SkillExtractor
from schemas import (
    EXPERIENCE_INDETERMINATE, EXPERIENCE_STATED, PRIORITY_PREFERRED, PRIORITY_REQUIRED,
    PRIORITY_UNSPECIFIED, REQUIREMENT_CERTIFICATION, REQUIREMENT_DEGREE, REQUIREMENT_EXPERIENCE,
    REQUIREMENT_SKILL, JobRequirement, Section,
)
from utils.links import is_link_line

_SECTION_PRIORITY = {
    "requirements": PRIORITY_REQUIRED,
    "preferred": PRIORITY_PREFERRED,
}
_REQUIRED_RE = re.compile(
    r"\b(?:required|must(?:\s+have|\s+be)?|minimum(?:\s+of)?|need to have)\b",
    re.IGNORECASE,
)
_PREFERRED_RE = re.compile(
    r"\b(?:preferred|nice[\s-]+to[\s-]+have|good to have|a plus|bonus|ideally|desired)\b",
    re.IGNORECASE,
)
_CONFLICT_NOTE = "The heading and the wording disagree, or the line says both, so the priority is unspecified."
_BOTH_LABELS_NOTE = "The posting labels this in more than one way, so the priority is unspecified."

_AMBIGUOUS_DEGREE = {"MA", "MS", "ME", "BA", "BE", "FA"}
_BARE_DEGREE_RE = re.compile(
    r"\b(bachelor(?:'s)?(?:\s+degree)?|master(?:'s)?(?:\s+degree)?|"
    r"ph\.?\s*d\.?|doctorate|doctoral(?:\s+degree)?|associate(?:'s)?(?:\s+degree)?)\b",
    re.IGNORECASE,
)
_TRAIL_PRIORITY_RE = re.compile(
    r"\s+(?:required|preferred|desired|or equivalent|is required|is preferred|a plus|is a plus)\b.*$",
    re.IGNORECASE,
)
_DEGREE_CUE_RE = re.compile(r"\b(?:degree|in|of)\b", re.IGNORECASE)

_CERT_RE = re.compile(r"\b(?:certification|certificate|certified)\b", re.IGNORECASE)
_GENERIC_CERT_RE = re.compile(
    r"^(?:professional\s+)?(?:certifications?|certificates?|certified)$",
    re.IGNORECASE,
)

# Longer phrases are requirements of their own. Masking them stops the shorter
# taxonomy skill ("React" inside "React hooks") from taking their place.
_PHRASES = (
    ("React hooks", re.compile(r"\breact(?:\.js|\s+js)?\s+hooks?\b", re.IGNORECASE)),
    ("functional programming", re.compile(
        r"\bfunctional\s+programming(?:\s+principles)?\b", re.IGNORECASE,
    )),
    ("state management", re.compile(
        r"\bstate[\s-]*management(?:\s+approaches|\s+libraries)?\b", re.IGNORECASE,
    )),
    ("Flux", re.compile(r"\bflux\b", re.IGNORECASE)),
    ("build automation", re.compile(r"\bbuild\s+automation\b", re.IGNORECASE)),
    ("testing", re.compile(r"\btesting\b", re.IGNORECASE)),
)
PHRASE_PATTERNS = {name: pattern for name, pattern in _PHRASES}

_NUM_YEARS_RE = re.compile(
    r"(?:(?P<prefix>\bat least\b|\bminimum(?:\s+of)?\b|\bmin\.)\s+)?"
    r"(?P<lo>\d+(?:\.\d+)?)"
    r"(?:\s*(?P<plus>\+|plus|or more))?"
    r"(?:\s*[-–—]\s*(?P<hi>\d+(?:\.\d+)?)|\s+to\s+(?P<hi2>\d+(?:\.\d+)?))?"
    r"\s*years?(?:'s|’s|')?\b",
    re.IGNORECASE,
)
_FOCUS_INTRO_RE = re.compile(
    r"\s*(?:of|with|in|using)\s+(?P<body>.+)",
    re.IGNORECASE,
)
_GENERIC_FOCUS = {
    "professional", "relevant", "hands-on", "hands", "work", "software",
    "industry", "commercial", "development", "the", "a", "an", "on",
}
_BULLET_RE = re.compile(r"^(?:[-*•]\s+)+")
_OR_BETWEEN_RE = re.compile(r"[\s,]*or(?:\s+similar)?[\s,]*", re.IGNORECASE)
_SLASH_BETWEEN_RE = re.compile(r"\s*/\s*")
# These names are one requirement when the posting states them as alternatives.
# Separate bullets without "or" stay separate requirements.
_EQUIVALENT_FAMILIES = (
    frozenset({"Redux", "Flux", "state management"}),
)
_TESTING_PREFIX_RE = re.compile(r"(?:unit|penetration|pen|a/b)\s+$", re.IGNORECASE)
_PROMO_LINE_RE = re.compile(
    r"\b(?:competitive salary|health insurance|paid time off|stock options|"
    r"gym membership|free snacks|on the job|equal opportunity|fast-growing|"
    r"join us|what we offer|perks include|medical insurance|dental insurance)\b",
    re.IGNORECASE,
)
# Requirement sections are still read even if a line happens to use promotional words.
_REQUIREMENT_SECTIONS = {"requirements", "preferred", "qualifications", "responsibilities", "skills"}
_SKIP_SECTIONS = {"promotional"}
_VAGUE_YEARS_RE = re.compile(
    r"\b(?:several|many|extensive|significant|some)\s+years?(?:'s|’s|')?"
    r"(?:\s+of(?:\s+(?!experience\b)[A-Za-z][\w.+#-]*)?)?\s+experience\b",
    re.IGNORECASE,
)
_FIELD_AFTER_DEGREE_RE = re.compile(
    r"^\s+(?:in|of)\s+([A-Za-z][A-Za-z&./'\- ]{1,80})",
    re.IGNORECASE,
)
_VAGUE_NOTE = "The posting mentions experience but does not state a number of years."
_MIXED_YEARS_NOTE = "The line states more than one duration, so the length is indeterminate."


def degree_level(text: Optional[str]) -> Optional[str]:
    """Map a degree phrase to doctorate, master, bachelor, or associate."""
    if not text:
        return None
    if re.search(r"\b(?:ph\.?\s*d\.?|doctorate|doctoral|doctor of)\b", text, re.IGNORECASE):
        return "doctorate"
    if re.search(
        r"\b(?:master(?:'s)?|mba|m\.?\s*sc|msc|m\.?\s*tech|m\.?\s*phil|m\.s\.?|ms)\b",
        text, re.IGNORECASE,
    ):
        return "master"
    if re.search(
        r"\b(?:bachelor(?:'s)?|b\.?\s*sc|bsc|b\.?\s*tech|btech|b\.s\.?|b\.a\.?|bs|ba)\b",
        text, re.IGNORECASE,
    ):
        return "bachelor"
    if re.search(r"\bassociate(?:'s)?\b", text, re.IGNORECASE):
        return "associate"
    return None


def classify_priority(section_name: str, line: str) -> Tuple[str, Optional[str]]:
    """Return ``(priority, note)``. A note is set only when the label is ambiguous."""
    section_priority = _SECTION_PRIORITY.get(section_name)
    says_required = bool(_REQUIRED_RE.search(line))
    says_preferred = bool(_PREFERRED_RE.search(line))
    if says_required and says_preferred:
        return PRIORITY_UNSPECIFIED, _CONFLICT_NOTE
    wording = PRIORITY_REQUIRED if says_required else PRIORITY_PREFERRED if says_preferred else None
    if section_priority and wording and section_priority != wording:
        return PRIORITY_UNSPECIFIED, _CONFLICT_NOTE
    if section_priority and wording:
        return section_priority, None
    if section_priority:
        return section_priority, None
    if wording:
        return wording, None
    return PRIORITY_UNSPECIFIED, None


def _clean_detail(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value).strip(" ,;:-")
    text = _TRAIL_PRIORITY_RE.sub("", text).strip(" ,;:-")
    return text or None


def _field_after(text: str) -> Optional[str]:
    match = _FIELD_AFTER_DEGREE_RE.match(text)
    if not match:
        return None
    return _clean_detail(match.group(1))


def _degree_on_line(line: str) -> Optional[Tuple[str, Optional[str]]]:
    found = _find_degree(line)
    if found:
        degree, field, span = found
        token = (degree or "").split()[0]
        ambiguous = degree in _AMBIGUOUS_DEGREE or token in _AMBIGUOUS_DEGREE
        if not (ambiguous and not _DEGREE_CUE_RE.search(line)):
            level = degree_level(degree)
            if level:
                return level, _clean_detail(field) or _field_after(line[span[1]:])
    bare = _BARE_DEGREE_RE.search(line)
    if not bare:
        return None
    level = degree_level(bare.group(1))
    if not level:
        return None
    return level, _field_after(line[bare.end():])


def _certification_on_line(line: str) -> Optional[str]:
    if not _CERT_RE.search(line):
        return None
    name = _clean_detail(re.sub(r"^\s*[-*•]\s*", "", line))
    if not name or _GENERIC_CERT_RE.match(name):
        return None
    return name


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _phrase_hits(line: str) -> List[Tuple[int, int, str, str]]:
    """``(start, end, canonical name, surface text)`` for explicit phrases."""
    found: List[Tuple[int, int, str, str]] = []
    for name, pattern in _PHRASES:
        for match in pattern.finditer(line):
            found.append((match.start(), match.end(), name, match.group()))
    found.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    kept: List[Tuple[int, int, str, str]] = []
    occupied: List[Tuple[int, int]] = []
    for start, end, name, surface in found:
        if any(not (end <= left or start >= right) for left, right in occupied):
            continue
        if name == "testing" and _TESTING_PREFIX_RE.search(line[max(0, start - 16):start]):
            continue
        kept.append((start, end, name, surface))
        occupied.append((start, end))
    return kept


def _mask_spans(line: str, spans: List[Tuple[int, int]]) -> str:
    chars = list(line)
    for start, end in spans:
        for index in range(start, min(end, len(chars))):
            chars[index] = " "
    return "".join(chars)


def _same_line(line: str, evidence_text: str) -> bool:
    if evidence_text == line:
        return True
    if evidence_text.endswith("...") and line.startswith(evidence_text[:-3]):
        return True
    return False


def _ignored_line(section_name: str, line: str) -> bool:
    """Benefits, company ads, and other promotional lines are not requirements."""
    if section_name in _SKIP_SECTIONS:
        return True
    if section_name in _REQUIREMENT_SECTIONS:
        return False
    return bool(_PROMO_LINE_RE.search(line))


def _skills_on_line(
    extractor: SkillExtractor, section_name: str, lines: List[str], index: int, masked_line: str,
) -> List[Tuple[str, str, str]]:
    """Taxonomy skills on this line, as ``(name, category, surface)``.

    ``masked_line`` has explicit phrases blanked out so a shorter skill inside
    one of those phrases is not extracted again.
    """
    start = max(0, index - 1)
    window_lines = [item.strip() for item in lines[start: index + 2]]
    window_lines[index - start] = masked_line
    found = extractor.extract([Section(
        name=section_name, heading=None, start_line=0, end_line=0, content="\n".join(window_lines),
    )])
    names: List[Tuple[str, str, str]] = []
    for skill in found:
        surface = None
        for item in skill.evidence:
            if _same_line(masked_line, item.text) or _same_line(masked_line.strip(), item.text):
                surface = item.matched_as or skill.name
                break
        if surface:
            names.append((skill.name, skill.category, surface))
    return names


def _tail_has_experience(tail: str) -> bool:
    words = re.findall(r"[A-Za-z']+", tail)
    return "experience" in [word.lower() for word in words[:8]]


def _focus_from_tail(tail: str, extractor: SkillExtractor, section_name: str) -> Optional[str]:
    """A skill named immediately after of/with/in/using, when the line states one."""
    match = _FOCUS_INTRO_RE.match(tail)
    if not match:
        return None
    body = re.split(r"\bexperience\b|[,.;]", match.group("body"), maxsplit=1, flags=re.IGNORECASE)[0]
    body = body.strip()
    if not body or body.lower() in _GENERIC_FOCUS:
        return None
    names = extractor.find_in_text(body, section_name)
    return names[0] if names else None


def _durations_on_line(
    line: str, extractor: SkillExtractor, section_name: str,
) -> List[Tuple[Optional[float], Optional[float], str, Optional[str], str, Optional[str]]]:
    """Each stated duration on the line.

    Two generic durations joined by "or" stay one indeterminate item. A line
    that states 3+ years of professional experience and 2+ years with a named
    skill stays two items. The last value is the skill the years apply to.
    """
    cleaned = _strip_bullet(line)
    matches = list(_NUM_YEARS_RE.finditer(cleaned))
    stated: List[Tuple[Optional[float], Optional[float], str, Optional[str], str, Optional[str]]] = []
    for index, match in enumerate(matches):
        next_start = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        tail = cleaned[match.end():next_start]
        tail = re.split(r"\bincluding\b|[,;]", tail, maxsplit=1, flags=re.IGNORECASE)[0]
        focus = _focus_from_tail(tail, extractor, section_name)
        if not _tail_has_experience(tail) and not focus:
            continue
        high_raw = match.group("hi") or match.group("hi2")
        high = float(high_raw) if high_raw else None
        phrase = cleaned[match.start():match.end() + len(tail)].strip(" ,;:-")
        stated.append((float(match.group("lo")), high, EXPERIENCE_STATED, None, phrase or cleaned, focus))
    if stated:
        generic = [item for item in stated if item[5] is None]
        lows = {item[0] for item in generic}
        if len(generic) == len(stated) and len(lows) > 1 and re.search(r"\bor\b", cleaned, re.IGNORECASE):
            return [(None, None, EXPERIENCE_INDETERMINATE, _MIXED_YEARS_NOTE, cleaned, None)]
        return stated
    if _VAGUE_YEARS_RE.search(cleaned):
        return [(None, None, EXPERIENCE_INDETERMINATE, _VAGUE_NOTE, cleaned, None)]
    return []


def _alternative_groups(
    line: str,
    phrases: List[Tuple[int, int, str, str]],
    skills: List[Tuple[str, str, str]],
) -> List[List[Tuple[str, Optional[str], str, int, int]]]:
    """Group skills joined only by an explicit ``or``.

    ``Python and SQL`` stays two requirements. ``Flux or Redux`` becomes one
    requirement whose alternatives are both names. ``or similar`` is accepted
    between a named skill and a following phrase.
    """
    occupied = [(start, end) for start, end, _name, _surface in phrases]
    placed: List[Tuple[int, int, str, Optional[str], str]] = [
        (start, end, name, None, surface) for start, end, name, surface in phrases
    ]
    for name, category, surface in skills:
        match = re.search(re.escape(surface), line, flags=re.IGNORECASE) if surface else None
        if match is None:
            continue
        if any(not (match.end() <= left or match.start() >= right) for left, right in occupied):
            continue
        placed.append((match.start(), match.end(), name, category, surface))
        occupied.append((match.start(), match.end()))
    placed.sort(key=lambda item: (item[0], item[1]))
    ordered: List[Tuple[str, Optional[str], str, int, int]] = []
    seen = set()
    for start, end, name, category, surface in placed:
        if name in seen:
            continue
        seen.add(name)
        ordered.append((name, category, surface, start, end))
    if not ordered:
        return []
    kinds = [_between_kind(line[previous[4]:current[3]]) for previous, current in zip(ordered, ordered[1:])]
    groups: List[List[Tuple[str, Optional[str], str, int, int]]] = []
    index = 0
    while index < len(ordered):
        group = [ordered[index]]
        cursor = index
        while cursor < len(kinds) and _joins_alternatives(kinds, cursor):
            group.append(ordered[cursor + 1])
            cursor += 1
        groups.append(group)
        index = cursor + 1
    return groups


def _between_kind(between: str) -> str:
    """How two neighboring skill names are joined.

    ``A or B`` and ``A/B`` are alternatives. ``A, B, or C`` is one alternative
    list. ``A, B or C`` keeps A separate from the B-or-C pair. ``A and B``
    stays two requirements.
    """
    if _SLASH_BETWEEN_RE.fullmatch(between or ""):
        return "or"
    if _OR_BETWEEN_RE.fullmatch(between or ""):
        if re.match(r"\s*,", between or ""):
            return "or-list"
        return "or"
    if re.fullmatch(r"[\s,]+", between or ""):
        return "comma"
    return "other"


def _joins_alternatives(kinds: List[str], index: int) -> bool:
    kind = kinds[index]
    if kind in {"or", "or-list"}:
        return True
    if kind != "comma":
        return False
    for later in kinds[index + 1:]:
        if later == "or-list":
            return True
        if later != "comma":
            return False
    return False


def _wording(line: str, surface: str, sole: bool) -> str:
    """Keep the whole line when it states one item, otherwise the matched words."""
    cleaned = _strip_bullet(line)
    if sole and cleaned:
        return cleaned
    return (surface or cleaned).strip()


def _merge(items: List[JobRequirement]) -> List[JobRequirement]:
    merged: Dict[Tuple, JobRequirement] = {}
    order: List[Tuple] = []
    for item in items:
        if item.kind == REQUIREMENT_SKILL:
            key = (REQUIREMENT_SKILL, item.skill_name, tuple(item.alternatives))
        elif item.kind == REQUIREMENT_DEGREE:
            key = (REQUIREMENT_DEGREE, item.degree_level, item.degree_field)
        elif item.kind == REQUIREMENT_CERTIFICATION:
            key = (REQUIREMENT_CERTIFICATION, (item.certification_name or "").lower())
        else:
            key = (
                REQUIREMENT_EXPERIENCE, item.experience_status, item.years_min,
                item.years_max, item.experience_focus,
            )
        previous = merged.get(key)
        if previous is None:
            merged[key] = item
            order.append(key)
            continue
        if previous.priority == item.priority:
            continue
        if previous.priority != PRIORITY_UNSPECIFIED and item.priority != PRIORITY_UNSPECIFIED:
            previous.priority = PRIORITY_UNSPECIFIED
            previous.note = _BOTH_LABELS_NOTE
            continue
        if previous.priority == PRIORITY_UNSPECIFIED:
            merged[key] = item
    return [merged[key] for key in order]


def _accepted_names(item: JobRequirement) -> List[str]:
    if item.alternatives:
        return list(item.alternatives)
    if item.skill_name:
        return [item.skill_name]
    return []


def _equivalent_family(names: List[str]) -> Optional[frozenset]:
    if not names:
        return None
    for family in _EQUIVALENT_FAMILIES:
        if all(name in family for name in names):
            return family
    return None


def _states_alternatives(item: JobRequirement) -> bool:
    if item.alternatives:
        return True
    return bool(re.search(r"\bor\b|/", item.text or "", re.IGNORECASE))


def _consolidate_alternatives(items: List[JobRequirement]) -> List[JobRequirement]:
    """Fold duplicate names into one explicit alternative requirement.

    ``Redux``, ``Flux``, and ``Redux or Flux`` become one requirement that
    either name can satisfy. ``Redux`` and ``Flux`` on their own, with no
    alternative wording, stay two requirements. React and React hooks are
    not equivalents.
    """
    result: List[JobRequirement] = []
    consumed = set()
    for index, item in enumerate(items):
        if index in consumed:
            continue
        names = _accepted_names(item)
        family = _equivalent_family(names) if item.kind == REQUIREMENT_SKILL else None
        if family is None:
            result.append(item)
            continue
        cluster = [index]
        for other_index, other in enumerate(items):
            if other_index == index or other.kind != REQUIREMENT_SKILL:
                continue
            if _equivalent_family(_accepted_names(other)) == family:
                cluster.append(other_index)
        members = [items[position] for position in cluster]
        if len(members) == 1 or not any(_states_alternatives(member) for member in members):
            result.append(item)
            continue
        for position in cluster:
            consumed.add(position)
        anchor = next((member for member in members if member.alternatives), members[0])
        union: List[str] = []
        for name in _accepted_names(anchor):
            union.append(name)
        for member in members:
            for name in _accepted_names(member):
                if name not in union:
                    union.append(name)
        priorities = {member.priority for member in members}
        note = anchor.note
        if PRIORITY_REQUIRED in priorities and PRIORITY_PREFERRED in priorities:
            priority = PRIORITY_UNSPECIFIED
            note = _BOTH_LABELS_NOTE
        elif PRIORITY_REQUIRED in priorities:
            priority = PRIORITY_REQUIRED
        elif PRIORITY_PREFERRED in priorities:
            priority = PRIORITY_PREFERRED
        else:
            priority = anchor.priority
        result.append(JobRequirement(
            kind=REQUIREMENT_SKILL,
            priority=priority,
            text=anchor.text,
            section=anchor.section,
            skill_name=union[0],
            skill_category=next((member.skill_category for member in members if member.skill_category), None),
            alternatives=union if len(union) > 1 else [],
            note=note,
        ))
    return result


def extract_requirements(sections: List[Section], extractor: SkillExtractor) -> List[JobRequirement]:
    """Extract requirements in document order. Link-only and promotional lines are skipped."""
    items: List[JobRequirement] = []
    for section in sections:
        lines = section.content.split("\n") if section.content else []
        for index, raw in enumerate(lines):
            line = raw.strip()
            if not line or is_link_line(line) or _ignored_line(section.name, line):
                continue
            priority, note = classify_priority(section.name, line)
            durations = _durations_on_line(line, extractor, section.name)
            focuses = {focus for _low, _high, _status, _years_note, _text, focus in durations if focus}
            phrases = _phrase_hits(line)
            masked = _mask_spans(line, [(start, end) for start, end, _name, _surface in phrases])
            skills = _skills_on_line(extractor, section.name, lines, index, masked)
            groups = _alternative_groups(line, phrases, skills)
            for group in groups:
                names = [name for name, _category, _surface, _start, _end in group]
                alternatives = names if len(names) > 1 else []
                name, category, surface, start, end = group[0]
                duration_only = bool(names) and all(skill_name in focuses for skill_name in names)
                if duration_only:
                    # The years stay on the experience requirement. The skill text is the name.
                    text = " or ".join(names) if alternatives else (surface or name)
                elif alternatives:
                    text = line[group[0][3]:group[-1][4]].strip(" ,;:-")
                else:
                    text = _wording(line, surface, len(groups) == 1)
                items.append(JobRequirement(
                    kind=REQUIREMENT_SKILL, priority=priority, text=text or surface,
                    section=section.name, skill_name=name, skill_category=category, note=note,
                    alternatives=alternatives,
                ))
            degree = _degree_on_line(line)
            if degree:
                level, field = degree
                items.append(JobRequirement(
                    kind=REQUIREMENT_DEGREE, priority=priority, text=line, section=section.name,
                    degree_level=level, degree_field=field, note=note,
                ))
            certification = _certification_on_line(line)
            if certification:
                items.append(JobRequirement(
                    kind=REQUIREMENT_CERTIFICATION, priority=priority, text=line, section=section.name,
                    certification_name=certification, note=note,
                ))
            for low, high, status, years_note, text, focus in durations:
                items.append(JobRequirement(
                    kind=REQUIREMENT_EXPERIENCE, priority=priority, text=text, section=section.name,
                    years_min=low, years_max=high, experience_status=status,
                    experience_focus=focus, note=years_note or note,
                ))
    return _consolidate_alternatives(_merge(items))
