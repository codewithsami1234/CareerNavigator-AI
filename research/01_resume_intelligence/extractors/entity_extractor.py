"""Rule-based extraction of structured entities from resume sections.

Everything here is a transparent heuristic (regular expressions + keyword lists).
Anything that cannot be determined is returned as ``None`` / an empty list. These
heuristics are a baseline: they work best on conventional, text-based layouts.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from schemas import (
    CertificationEntry, ContactInfo, EducationEntry, ExperienceEntry, ProjectEntry, Section,
)
from utils.links import is_link_line, urls
from .section_extractor import section_text

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
_BULLET_RE = re.compile(r"^\s*[-*•▪●◦■□►▶➢➤·‣⁃∙○]\s*(?=\S)")
_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
_DATE = rf"(?:(?:{_MONTH}\.?,?\s+)?(?:19|20)\d{{2}}|(?:0?[1-9]|1[0-2])/(?:19|20)\d{{2}})"
_PRESENT = r"(?:Present|Current|Now|Ongoing|Till\s+date|To\s+date|Today)"
_RANGE_RE = re.compile(
    rf"(?P<start>{_DATE})\s*(?:-|–|—|to|until)\s*(?P<end>(?:(?:Expected|Anticipated)\s+)?{_DATE}|{_PRESENT})", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_SEPARATOR_RE = re.compile(r"\s*[|•·]\s*|\s+[–—-]\s+|\s{2,}")


def _is_bullet(line: str) -> bool:
    return bool(_BULLET_RE.match(line))


def _strip_bullet(line: str) -> str:
    return _BULLET_RE.sub("", line).strip()


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t,;:|•·–—-()[]")
    return value or None


def _lines(text: str) -> List[str]:
    return text.split("\n") if text else []


def _description_from(lines: List[str]) -> List[str]:
    """Strip bullets and re-join wrapped lines (a lowercase-start line continues the previous one)."""
    out: List[str] = []
    for line in lines:
        if not line.strip():
            continue
        bullet = _is_bullet(line)
        text = _strip_bullet(line)
        if not bullet and out and text[:1].islower():
            out[-1] = out[-1] + " " + text
        else:
            out.append(text)
    return out


# ---------------------------------------------------------------------------
# Contact information
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?<![\w.])(\+?\d[\d\s().\-]{8,}\d)(?![\w])")
_LINKEDIN_RE = re.compile(r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/[^\s,;|)]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[^\s,;|)]+", re.IGNORECASE)
# Profile-shaped URLs: one account segment, no repository or problem path.
_GITHUB_PROFILE_RE = re.compile(
    r"(?<![\w.])(?:https?://)?(?:www\.)?github\.com/(?P<user>[A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/?(?=$|[\s,;|)])",
    re.IGNORECASE)
_LEETCODE_PROFILE_RE = re.compile(
    r"(?<![\w.])(?:https?://)?(?:www\.)?leetcode\.com/(?:u/)?(?P<user>[A-Za-z0-9_-]{2,40})/?(?=$|[\s,;|)])",
    re.IGNORECASE)
_X_PROFILE_RE = re.compile(
    r"(?<![\w.])(?:https?://)?(?:www\.|mobile\.)?(?:x|twitter)\.com/(?P<user>[A-Za-z0-9_]{1,15})/?(?=$|[\s,;|)])",
    re.IGNORECASE)
_RESERVED_GITHUB = {"orgs", "topics", "features", "about", "pricing", "login", "settings", "marketplace"}
_RESERVED_LEETCODE = {"problems", "contest", "explore", "discuss", "problemset", "studyplan", "u"}
_RESERVED_X = {"home", "i", "intent", "share", "search", "explore", "login", "hashtag", "settings"}
_PROFILE_LABELS = {
    "linkedin": re.compile(r"^\s*linked\s*in\b", re.IGNORECASE),
    "github": re.compile(r"^\s*git\s*hub\b", re.IGNORECASE),
    "leetcode": re.compile(r"^\s*leet\s*code\b", re.IGNORECASE),
    "twitter": re.compile(r"^\s*(?:x\b|twitter\b|x\s*\(\s*twitter\s*\))", re.IGNORECASE),
}


def _profile_match(regex, reserved, value: str) -> Optional[str]:
    for m in regex.finditer(value):
        if m.group("user").lower() not in reserved:
            return m.group(0).rstrip(".")
    return None


def _from_links(kind: str, links) -> Optional[str]:
    """A profile URI stored in the file (e.g. a PDF annotation behind the word ``GitHub``).

    Only a profile-shaped target is accepted. A label without a stored target
    returns ``None``; no URL is ever composed from a label or a user name.
    """
    checks = {
        "linkedin": lambda uri: (_LINKEDIN_RE.search(uri) or [None])[0],
        "github": lambda uri: _profile_match(_GITHUB_PROFILE_RE, _RESERVED_GITHUB, uri),
        "leetcode": lambda uri: _profile_match(_LEETCODE_PROFILE_RE, _RESERVED_LEETCODE, uri),
        "twitter": lambda uri: _profile_match(_X_PROFILE_RE, _RESERVED_X, uri),
    }
    labelled, other = [], []
    for link in links or []:
        uri = (getattr(link, "uri", "") or "").strip()
        found = checks[kind](uri) if uri else None
        if not found:
            continue
        text = getattr(link, "text", "") or ""
        (labelled if _PROFILE_LABELS[kind].match(text) else other).append(found)
    picked = (labelled or other or [None])[0]
    return picked.rstrip(".") if picked else None


def without_link_lines(text: str) -> str:
    """Drop lines that only hold labelled URLs (``GitHub: ...``, ``Live Demo: ...``)."""
    return "\n".join(line for line in _lines(text) if not _is_link_line(line))
_LOCATION_LABEL_RE = re.compile(r"^(?:location|address|city|based in)\s*[:\-]\s*(?P<v>.+)$", re.IGNORECASE)
_NAME_LABEL_RE = re.compile(r"^name\s*[:\-]\s*(?P<v>.+)$", re.IGNORECASE)
_CITY_REGION_RE = re.compile(
    r"^[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'\- ]{1,40},\s*[A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ.'\- ]{1,40}$"
)
_NAME_STOPWORDS = {
    "resume", "cv", "curriculum", "vitae", "profile", "summary", "objective", "engineer", "developer",
    "analyst", "manager", "designer", "intern", "student", "scientist", "consultant", "architect",
    "specialist", "administrator", "programmer", "university", "college", "contact", "skills",
    "experience", "education", "projects", "email", "phone", "address", "engineering", "developer,",
}
_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ.'’\-]*(?: [A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ.'’\-]*){1,3}$")


def _phone_candidates(text: str) -> List[str]:
    found = []
    for m in _PHONE_RE.finditer(text):
        cand = m.group(1).strip()
        digits = re.sub(r"\D", "", cand)
        if not 10 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}", cand):
            continue
        found.append(cand)
    return found


def _looks_like_name(line: str) -> bool:
    line = line.strip()
    if not 3 <= len(line) <= 50 or any(ch.isdigit() for ch in line) or "@" in line:
        return False
    if not _NAME_RE.match(line):
        return False
    words = [w.strip(".,").lower() for w in line.split()]
    if any(w in _NAME_STOPWORDS for w in words):
        return False
    return all(w[0].isupper() for w in line.split())


def extract_contact(text: str, sections: List[Section], links=None) -> ContactInfo:
    """Contact details. ``links`` are optional hyperlink targets stored in the file.

    Profile URLs come from visible text first. A stored hyperlink is used only
    when the visible text has none. A GitHub repository URL in a project is not
    a profile, so it is not reported as the GitHub contact.
    """
    contact = ContactInfo()
    head_blocks = [s for s in sections if s.name in ("header", "contact")]
    head_text = "\n".join(s.content for s in head_blocks)
    head_lines = [l.strip() for l in head_text.split("\n") if l.strip()]

    m = _EMAIL_RE.search(head_text) or _EMAIL_RE.search(text)
    contact.email = m.group(0) if m else None

    phones = _phone_candidates(head_text) or _phone_candidates(text)
    contact.phone = phones[0] if phones else None

    m = _LINKEDIN_RE.search(text)
    contact.linkedin = m.group(0).rstrip(".") if m else _from_links("linkedin", links)
    m = _GITHUB_RE.search(head_text)
    contact.github = (
        (m.group(0).rstrip(".") if m else None)
        or _profile_match(_GITHUB_PROFILE_RE, _RESERVED_GITHUB, text)
        or _from_links("github", links)
    )
    contact.leetcode = (
        _profile_match(_LEETCODE_PROFILE_RE, _RESERVED_LEETCODE, text) or _from_links("leetcode", links)
    )
    contact.twitter = _profile_match(_X_PROFILE_RE, _RESERVED_X, text) or _from_links("twitter", links)

    # Name: explicit label first, otherwise the first plausible line near the top.
    for line in head_lines[:8]:
        lm = _NAME_LABEL_RE.match(line)
        if lm and _looks_like_name(lm.group("v")):
            contact.name = lm.group("v").strip()
            break
    if contact.name is None:
        for line in head_lines[:5]:
            if _looks_like_name(line):
                contact.name = line
                break

    # Location: only when explicitly labelled, or a "City, Region" piece of a contact line.
    for line in head_lines:
        lm = _LOCATION_LABEL_RE.match(line)
        if lm:
            contact.location = _clean(lm.group("v"))
            break
    if contact.location is None:
        for line in head_lines:
            if not (_EMAIL_RE.search(line) or _phone_candidates(line)):
                continue
            for seg in re.split(r"\s*[|•·]\s*", line):
                seg = seg.strip()
                if not re.search(r"[\d@/]", seg) and _CITY_REGION_RE.match(seg):
                    contact.location = seg
                    break
            if contact.location:
                break
    return contact


# ---------------------------------------------------------------------------
# Education
# ---------------------------------------------------------------------------
_ABBREVS = [
    "BSCS", "BSIT", "BSSE", "BSEE", "MSCS", "MSIT", "MSSE", "BSc", "B.Sc.", "B.Sc", "BS", "B.S.", "B.S",
    "BE", "B.E.", "B.E", "BTech", "B.Tech.", "B.Tech", "BA", "B.A.", "B.A", "BBA", "BCA", "BCom", "B.Com",
    "MSc", "M.Sc.", "M.Sc", "MS", "M.S.", "M.S", "ME", "M.E.", "MTech", "M.Tech.", "M.Tech", "MA", "M.A.",
    "M.A", "MBA", "MCA", "MPhil", "M.Phil", "PhD", "Ph.D.", "Ph.D", "FSc", "F.Sc.", "F.Sc", "FA", "ICS",
    "HSSC", "SSC", "A-Levels", "A-Level", "O-Levels", "O-Level",
]
_AMBIGUOUS_ABBREVS = {"MA", "MS", "ME", "BA", "BE", "FA"}
_FIELD_WORDS = re.compile(
    r"\b(science|engineering|technology|arts|business|computer|information|software|management|studies|"
    r"mathematics|physics|commerce|administration|data|security|systems)\b", re.IGNORECASE)
_ABBREV_RE = re.compile(
    r"(?<![A-Za-z0-9.])(?:" + "|".join(re.escape(a) for a in sorted(_ABBREVS, key=len, reverse=True))
    + r")(?![A-Za-z0-9])")
_FULL_DEGREE_RE = re.compile(
    r"\b(?P<level>Bachelor|Master|Doctor|Associate)(?:'?s)?(?:\s+Degree)?\s+(?P<prep>of|in)\s+"
    r"(?P<rest>[A-Za-z&.'\- ]{2,80}?)"
    r"(?=\s*(?:[,|(\[]|\s[–—-]\s|\b(?:19|20)\d{2}\b|\bfrom\b|\bat\b|\bCGPA\b|\bGPA\b|$))")
_LEVEL_RE = re.compile(
    r"\b(?P<deg>Diploma(?:\s+(?:of|in)\s+[A-Z][A-Za-z&/\- ]{2,50}?)?"
    r"|Intermediate(?:\s+(?:of|in)\s+[A-Z][A-Za-z&/\- ]{2,50}?)?"
    r"|Higher Secondary(?: School)?(?: Certificate)?|Matriculation|Matric|High School Diploma|Associate Degree)"
    r"(?=\s*(?:[,|(\[]|\s[–—-]\s|\b(?:19|20)\d{2}\b|\bfrom\b|\bat\b|$))")
_TYPE_RE = re.compile(
    r"^(?P<type>Science|Arts|Technology|Engineering|Business Administration|Fine Arts|Philosophy|Commerce|"
    r"Education|Computer Applications|Applied Science|Laws)(?:\s+(?:in|of)\s+(?P<field>.+))?$", re.IGNORECASE)
_FIELD_AFTER_ABBREV_RE = re.compile(
    r"^\s*(?:\(\s*(?P<p>[^)]{2,60}?)\s*\)|(?:[-–—:,]\s*|(?:in|of)\s+)?(?P<f>[A-Z][A-Za-z&/'\- ]{2,70}?))"
    r"(?=\s*(?:[,|(\[]|\s[–—-]\s|\b(?:19|20)\d{2}\b|\bfrom\b|\bat\b|\bCGPA\b|\bGPA\b|$))")
_INSTITUTION_RE = re.compile(
    r"\b(University|Universit[äée]t?|College|Institute|Institution|Polytechnic|Academy|School)\b", re.IGNORECASE)
_GPA_RE = re.compile(r"\b(?:C?GPA|Grade)\s*[:\-]?\s*(\d(?:\.\d{1,2})?(?:\s*/\s*\d(?:\.\d+)?)?)", re.IGNORECASE)
_EXPECTED_RE = re.compile(r"\b(expected|anticipated|pursuing|in progress)\b", re.IGNORECASE)


def _find_degree(line: str) -> Optional[Tuple[str, Optional[str], Tuple[int, int]]]:
    """Return (degree, field_of_study, span) for the first degree found in ``line``."""
    m = _FULL_DEGREE_RE.search(line)
    if m:
        level, prep, rest = m.group("level"), m.group("prep"), m.group("rest").strip(" .")
        tm = _TYPE_RE.match(rest) if prep.lower() == "of" else None
        if tm:
            degree = f"{level} of {tm.group('type').title()}"
            fld = _clean(tm.group("field"))
        else:
            degree = f"{level} {prep} {rest}"
            fld = _clean(rest)
        end = m.end()
        if fld is None:
            pm = re.match(r"\s*\(([^)]{2,60})\)", line[m.end():])
            if pm and not re.search(r"\d", pm.group(1)):
                fld = _clean(pm.group(1))
                end = m.end() + pm.end()
        return degree, fld, (m.start(), end)

    for am in _ABBREV_RE.finditer(line):
        token = am.group(0)
        if token in _AMBIGUOUS_ABBREVS:
            before = line[:am.start()]
            if before.rstrip().endswith(",") and not _FIELD_WORDS.search(before):
                continue     # probably a US state ("Boston, MA")
        tail = line[am.end():]
        fld = None
        fm = _FIELD_AFTER_ABBREV_RE.match(tail)
        if fm:
            cand = _clean(fm.group("p") or fm.group("f"))
            if cand and not re.search(r"\d", cand) and not _INSTITUTION_RE.search(cand):
                fld = cand
        end = am.end() + (fm.end() if (fm and fld) else 0)
        return token, fld, (am.start(), end)

    lm = _LEVEL_RE.search(line)
    if lm:
        deg = _clean(lm.group("deg"))
        fld = None
        fm = re.search(r"\b(?:in|of)\s+([A-Z][A-Za-z&/\- ]{2,50})$", deg or "")
        if fm and deg:
            fld = _clean(fm.group(1))
        return deg or lm.group("deg"), fld, lm.span()
    return None


def _split_education_entries(lines: List[str]) -> List[List[str]]:
    entries: List[List[str]] = []
    cur: List[str] = []
    has_deg = has_inst = False
    after_blank = False
    for line in lines:
        if not line.strip():
            after_blank = True
            continue
        bullet = _is_bullet(line)
        is_deg = (not bullet) and _find_degree(line) is not None
        is_inst = (not bullet) and bool(_INSTITUTION_RE.search(line))
        new_entry = False
        if cur and not bullet:
            if (is_deg and has_deg) or (is_inst and has_inst):
                new_entry = True
            elif after_blank and (is_deg or is_inst) and (has_deg or has_inst):
                new_entry = True
        if new_entry:
            entries.append(cur)
            cur, has_deg, has_inst = [], False, False
        cur.append(line)
        has_deg = has_deg or is_deg
        has_inst = has_inst or is_inst
        after_blank = False
    if cur:
        entries.append(cur)
    return entries


def _parse_education_entry(lines: List[str]) -> Optional[EducationEntry]:
    entry = EducationEntry(raw_text="\n".join(lines))
    body = [l for l in lines if not _is_bullet(l)]

    spans = {}
    for idx, line in enumerate(body):
        found = _find_degree(line)
        if found:
            if entry.degree is None:
                entry.degree, entry.field_of_study = found[0], found[1]
            spans[idx] = found[2]

    # Institution: first segment that contains an institution keyword.
    for idx, line in enumerate(body):
        work = line
        if idx in spans:
            work = work[:spans[idx][0]] + " | " + work[spans[idx][1]:]
        work = _RANGE_RE.sub(" | ", work)
        work = _YEAR_RE.sub(" ", work)
        work = _GPA_RE.sub(" ", work)
        for seg in re.split(r"\s*[|•·]\s*|\s+[–—-]\s+|\s{2,}|[()]", work):
            seg = re.sub(r"^(?:at|from)\s+", "", seg.strip(" ,;:-"), flags=re.IGNORECASE)
            if seg and _INSTITUTION_RE.search(seg):
                parts = [p.strip() for p in seg.split(",") if p.strip()]
                seg = next((p for p in parts if _INSTITUTION_RE.search(p)), "")
                if seg:
                    entry.institution = seg
                    break
        if entry.institution:
            break

    if entry.degree is None and entry.institution is None:
        return None

    text = "\n".join(body)
    rm = _RANGE_RE.search(text)
    expected = bool(_EXPECTED_RE.search(text))
    if rm:
        entry.start_year = int(_YEAR_RE.search(rm.group("start")).group(0))
        end_raw = rm.group("end")
        ym = _YEAR_RE.search(end_raw)
        if ym:
            entry.end_year = int(ym.group(0))
            entry.ongoing = expected or None
        else:
            entry.ongoing = True
    else:
        years = _YEAR_RE.findall(text)
        if len(years) == 1:
            entry.end_year = int(years[0])
            entry.ongoing = True if expected else None
    if entry.end_year and not entry.ongoing:
        entry.graduation_year = entry.end_year
    if entry.ongoing is None and (entry.end_year or entry.start_year):
        entry.ongoing = False
    gm = _GPA_RE.search(text)
    if gm:
        entry.gpa = re.sub(r"\s+", "", gm.group(1))
    return entry


def extract_education(sections: List[Section]) -> List[EducationEntry]:
    text = section_text(sections, "education")
    if not text:
        return []
    entries = []
    for block in _split_education_entries(_lines(text)):
        parsed = _parse_education_entry(block)
        if parsed:
            entries.append(parsed)
    return entries


# ---------------------------------------------------------------------------
# Experience
# ---------------------------------------------------------------------------
_TITLE_RE = re.compile(
    r"\b(engineer|developer|programmer|intern|internship|trainee|analyst|manager|designer|consultant|"
    r"assistant|lead|specialist|administrator|architect|scientist|officer|coordinator|researcher|"
    r"associate|director|tester|technician|executive|representative|freelanc\w*|instructor|tutor|"
    r"teacher|lecturer|head|supervisor|president|founder|co-founder|owner|volunteer|apprentice|fellow)\b",
    re.IGNORECASE)
_ORG_RE = re.compile(
    r"\b(inc|llc|ltd|limited|pvt|corp|corporation|co|company|technologies|technology|solutions|systems|"
    r"software|labs?|university|institute|group|bank|studios?|agency|services|consulting|enterprises|"
    r"foundation|school|college|hospital|ventures|networks|soft|tech)\b\.?", re.IGNORECASE)
_EMPLOYMENT_TYPE_RE = re.compile(
    r"^(full[- ]?time|part[- ]?time|contract|remote|hybrid|on[- ]?site|freelance|internship)$", re.IGNORECASE)


def _headerish(line: str) -> bool:
    s = line.strip()
    return bool(s) and not _is_bullet(s) and len(s) <= 90 and not s.endswith(".") \
        and not s[:1].islower() and len(s.split()) <= 12


def _parse_job_header(header_lines: List[str]) -> dict:
    joined = " | ".join(l.strip() for l in header_lines if l.strip())
    out = {"title": None, "organization": None, "start_date": None, "end_date": None, "is_current": None}
    rm = _RANGE_RE.search(joined)
    if rm:
        out["start_date"] = _clean(rm.group("start"))
        out["end_date"] = _clean(rm.group("end"))
        out["is_current"] = bool(re.fullmatch(_PRESENT, rm.group("end").strip(), re.IGNORECASE))
        joined = joined[:rm.start()] + " | " + joined[rm.end():]
    joined = re.sub(r"\(\s*\)", " ", joined)

    segments: List[str] = []
    for seg in _SEPARATOR_RE.split(joined):
        seg = _clean(seg)
        if not seg or _EMPLOYMENT_TYPE_RE.match(seg):
            continue
        am = re.match(r"^(?P<t>.+?)\s+(?:at|@)\s+(?P<o>.+)$", seg, re.IGNORECASE)
        if am and _TITLE_RE.search(am.group("t")):
            segments.extend([am.group("t"), am.group("o")])
        else:
            segments.append(seg)
    if len(segments) == 1 and "," in segments[0]:
        segments = [s for s in (_clean(p) for p in segments[0].split(",", 1)) if s]

    titles = [s for s in segments if _TITLE_RE.search(s)]
    out["title"] = titles[0] if titles else None
    others = [s for s in segments if s != out["title"]]
    org_like = [s for s in others if _ORG_RE.search(s)]
    out["organization"] = (org_like or others or [None])[0]
    return out


def _split_experience(lines: List[str]) -> List[Tuple[List[str], List[str]]]:
    """Return [(header_lines, body_lines)] using date ranges as anchors."""
    anchors = [i for i, l in enumerate(lines)
               if l.strip() and not _is_bullet(l) and _RANGE_RE.search(l)]
    if not anchors:
        return _split_by_blocks(lines)

    header_starts = []
    for k, a in enumerate(anchors):
        floor = anchors[k - 1] if k else -1
        start, j, count = a, a - 1, 0
        while j > floor and count < 2 and _headerish(lines[j]):
            start, j, count = j, j - 1, count + 1
        header_starts.append(start)

    entries = []
    for k, a in enumerate(anchors):
        end = header_starts[k + 1] if k + 1 < len(anchors) else len(lines)
        header = lines[header_starts[k]: a + 1]
        body_start = a + 1
        probe = _parse_job_header(header)
        if (probe["title"] is None or probe["organization"] is None) \
                and body_start < end and _headerish(lines[body_start]):
            header.append(lines[body_start])
            body_start += 1
        entries.append((header, lines[body_start:end]))
    return entries


def _split_by_blocks(lines: List[str]) -> List[Tuple[List[str], List[str]]]:
    blocks, cur = [], []
    for line in lines:
        if line.strip():
            cur.append(line)
        elif cur:
            blocks.append(cur)
            cur = []
    if cur:
        blocks.append(cur)
    result = []
    for block in blocks:
        if _is_bullet(block[0]):
            continue
        result.append(([block[0]], block[1:]))
    return result


def extract_experience(sections: List[Section]) -> List[ExperienceEntry]:
    text = section_text(sections, "experience")
    if not text:
        return []
    entries = []
    for header, body in _split_experience(_lines(text)):
        info = _parse_job_header(header)
        if not any([info["title"], info["organization"], info["start_date"]]):
            continue
        entries.append(ExperienceEntry(
            organization=info["organization"], title=info["title"],
            start_date=info["start_date"], end_date=info["end_date"], is_current=info["is_current"],
            description=_description_from(body),
            raw_text="\n".join(header + body),
        ))
    return entries


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
_LABEL_LINE_RE = re.compile(
    r"^(tech(?:nologies|nology)?|tools?|stack|tech stack|built with|github|link|url|role|duration|"
    r"description|environment|live demo|demo|website|repo(?:sitory)?|source(?: code)?)\s*[:\-]", re.IGNORECASE)
_PROJECT_PREFIX_RE = re.compile(r"^(?:project\s*\d*\s*[:\-–]\s*|\d{1,2}[.)]\s+)", re.IGNORECASE)
_urls = urls
_is_link_line = is_link_line


def _title_like(line: str) -> bool:
    s = line.strip()
    return bool(s) and not _is_bullet(s) and len(s) <= 100 and not s.endswith(".") \
        and (s[0].isupper() or s[0].isdigit()) and len(s.split()) <= 14 and not _LABEL_LINE_RE.match(s)


def _split_project_title(line: str) -> List[str]:
    """``[name, rest]``. A pipe, when present, is the stack separator, so a dash
    before it stays in the name (``DSA — Data Structures | C++``)."""
    s = _PROJECT_PREFIX_RE.sub("", line.strip())
    if "|" in s:
        return [part for part in re.split(r"\s*\|\s*", s, maxsplit=1)]
    return re.split(r"\s+[–—-]\s+", s, maxsplit=1)


def _project_name(line: str) -> Optional[str]:
    s = _split_project_title(line)[0]
    s = _RANGE_RE.sub(" ", s)
    if "|" not in line:
        s = re.split(r"\s*\(", s)[0]
    return _clean(s)


def extract_projects(sections: List[Section]) -> List[ProjectEntry]:
    text = section_text(sections, "projects")
    if not text:
        return []
    lines = _lines(text)

    def next_is_content(i: int) -> bool:
        for nxt in lines[i + 1:]:
            if nxt.strip():
                return _is_bullet(nxt) or nxt.strip().endswith(".") or bool(_LABEL_LINE_RE.match(nxt.strip()))
        return False

    groups: List[dict] = []
    cur: Optional[dict] = None
    prev_blank, prev_bullet = True, False
    for i, line in enumerate(lines):
        if not line.strip():
            prev_blank = True
            continue
        bullet = _is_bullet(line)
        start_new = cur is None
        if cur is not None and not bullet and _title_like(line):
            if prev_blank or (prev_bullet and next_is_content(i)):
                start_new = True
        if start_new:
            cur = {"title": None if bullet else line, "body": [line] if bullet else []}
            groups.append(cur)
        else:
            cur["body"].append(line)
        prev_blank, prev_bullet = False, bullet

    entries = []
    for g in groups:
        raw = "\n".join(([g["title"]] if g["title"] else []) + g["body"])
        desc_lines = [line for line in g["body"] if not _is_link_line(line)]
        if g["title"]:
            rest = _split_project_title(g["title"])
            if len(rest) > 1 and rest[1].strip():
                desc_lines.insert(0, rest[1].strip())
        links: List[str] = []
        for url in _urls(raw):
            if url not in links:
                links.append(url)
        entries.append(ProjectEntry(
            name=_project_name(g["title"]) if g["title"] else None,
            description=_description_from(desc_lines),
            raw_text=raw,
            links=links,
        ))
    return entries


# ---------------------------------------------------------------------------
# Certifications and courses
# ---------------------------------------------------------------------------
_DATE_PAREN_RE = re.compile(rf"\(\s*(?:{_MONTH}\.?,?\s+)?(?:19|20)\d{{2}}\s*\)", re.IGNORECASE)
_ISSUER_DASH_RE = re.compile(r"\s[–—-]\s")


def _clean_balanced(value: Optional[str]) -> Optional[str]:
    """Like ``_clean`` but keeps balanced brackets such as ``(AI-900)``."""
    if value is None:
        return None
    value = re.sub(r"\s+", " ", value).strip(" \t,;:|•·–—-")
    while value.endswith(")") and value.count(")") > value.count("("):
        value = value[:-1].rstrip(" \t,;:|•·–—-")
    while value.startswith("(") and value.count("(") > value.count(")"):
        value = value[1:].lstrip(" \t,;:|•·–—-")
    if value.startswith("(") and value.endswith(")") and value.count("(") == 1:
        value = value[1:-1].strip()
    return value or None


def _parse_cert_line(text: str, kind: str) -> CertificationEntry:
    year_m = _YEAR_RE.findall(text)
    year = int(year_m[-1]) if year_m else None
    work = _DATE_PAREN_RE.sub(" ", text)
    work = _YEAR_RE.sub(" ", work) if year else work
    parts = [p for p in (_clean_balanced(x) for x in re.split(
        r"\s+[–—-]\s+|\s*\|\s*|\s+by\s+|\s+issued by\s+|\s*,\s*(?=[A-Z])", work)) if p]
    name = parts[0] if parts else _clean(text)
    issuer = parts[1] if len(parts) > 1 else None
    return CertificationEntry(name=name, issuer=issuer, year=year, kind=kind, raw_text=text)


def _split_cert_items(item: str) -> List[str]:
    """``A — X (2025)  |  B — Y (2026)`` holds two certificates when every piece has its own issuer dash."""
    pieces = [p.strip() for p in re.split(r"\s+\|\s+", item) if p.strip()]
    if len(pieces) > 1 and all(_ISSUER_DASH_RE.search(p) for p in pieces):
        return pieces
    return [item]


def extract_certifications(sections: List[Section]) -> List[CertificationEntry]:
    entries: List[CertificationEntry] = []
    for sec_name, kind in (("certifications", "certification"), ("courses", "course")):
        text = section_text(sections, sec_name)
        for item in _description_from(_lines(text)):
            for piece in _split_cert_items(item):
                if len(piece) >= 3:
                    entries.append(_parse_cert_line(piece, kind))
    return entries
