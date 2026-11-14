"""Compare job requirements with a resume analysis.

A skill match copies the resume evidence and keeps ``used`` or ``mentioned``.
Proficiency is not inferred from a mention. Related is a short list of
alternatives (for example PyTorch and TensorFlow), not every skill in the
same category, and it is not a match. Experience length uses explicit start
and end dates on employment entries only. Project mentions do not prove years
or professional employment. Without those dates the outcome is indeterminate.
"""
from __future__ import annotations

import calendar
import re
from datetime import date
from typing import List, Optional, Tuple

import config
from extractors.skill_extractor import mask_contact_tokens
from job_analysis.requirements import PHRASE_PATTERNS, degree_level
from schemas import (
    EXPERIENCE_STATED, OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED,
    REQUIREMENT_CERTIFICATION, REQUIREMENT_DEGREE, REQUIREMENT_EXPERIENCE, REQUIREMENT_SKILL,
    EducationEntry, ExperienceEntry, JobAnalysis, JobRequirement, MatchReport, RequirementMatch,
    ResumeAnalysis, STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_SUCCESS, SkillEvidence,
)

_PRESENT_RE = re.compile(
    r"^(?:present|current|now|ongoing|till date|to date|today)$",
    re.IGNORECASE,
)
_MONTH_YEAR_RE = re.compile(
    r"^(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\.?,?\s+(?P<year>(?:19|20)\d{2})$",
    re.IGNORECASE,
)
_YEAR_ONLY_RE = re.compile(r"^(?:19|20)\d{2}$")
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_STOP_STATUSES = (STATUS_FAILED, STATUS_EMPTY, STATUS_NEEDS_OCR)
_DURATION_WARNING = (
    "Experience length adds dated jobs together. Overlapping dates are not removed, "
    "and a job without an explicit start and end is not given a guessed length. "
    "Project mentions are not counted as professional experience."
)
# Same-category skills are not substitutes. Only these pairs are reported as
# related, and a related result is never a match. JavaScript/TypeScript,
# GitHub/GitLab, Node.js/REST API, and Azure/Docker/CI-CD are intentionally
# absent: evidence of one does not count as evidence of the other.
_RELATED_GROUPS = (
    frozenset({"PyTorch", "TensorFlow", "Keras", "scikit-learn"}),
    frozenset({"Docker", "Kubernetes"}),
)


def _clip(text: str) -> str:
    text = " ".join(text.split())
    limit = config.EVIDENCE_TEXT_MAX_CHARS
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _fields_match(required: Optional[str], stated: Optional[str]) -> str:
    """``yes``, ``no``, or ``unknown`` when the resume does not state a field."""
    if not required:
        return "yes"
    if not stated:
        return "unknown"
    wanted = _norm(required)
    have = _norm(stated)
    if not wanted or not have:
        return "unknown"
    if wanted == have:
        return "yes"
    if re.search(r"(?<![a-z0-9])" + re.escape(wanted) + r"(?![a-z0-9])", have):
        return "yes"
    return "no"


def _certs_match(job_name: str, resume_name: str) -> bool:
    job_norm = _norm(job_name)
    resume_norm = _norm(resume_name)
    if len(job_norm) < 6 or len(resume_norm) < 6:
        return False
    return job_norm in resume_norm or resume_norm in job_norm


def _month_number(token: str) -> int:
    return _MONTHS[token.lower()[:3]]


def _parse_point(value: Optional[str], *, is_end: bool, as_of: date) -> Optional[date]:
    if not value:
        return None
    text = " ".join(value.split())
    if _PRESENT_RE.match(text):
        return as_of
    month_year = _MONTH_YEAR_RE.match(text)
    if month_year:
        year = int(month_year.group("year"))
        month = _month_number(month_year.group("mon"))
        if is_end:
            return date(year, month, calendar.monthrange(year, month)[1])
        return date(year, month, 1)
    if _YEAR_ONLY_RE.match(text):
        year = int(text)
        return date(year, 12, 31) if is_end else date(year, 1, 1)
    return None


def _duration_years(entry: ExperienceEntry, as_of: date) -> Optional[float]:
    start = _parse_point(entry.start_date, is_end=False, as_of=as_of)
    end = _parse_point(entry.end_date, is_end=True, as_of=as_of)
    if start is None or end is None or end < start:
        return None
    return (end - start).days / 365.25


def _snippet(text: str, match: "re.Match[str]") -> str:
    start = max(0, match.start() - 60)
    end = min(len(text), match.end() + 60)
    return _clip(text[start:end].strip())


def _resume_snippets(resume: ResumeAnalysis) -> List[Tuple[str, str, str]]:
    """``(section, text, evidence_type)`` lines that can support a phrase."""
    rows: List[Tuple[str, str, str]] = []
    for skill in resume.skills:
        for item in skill.evidence:
            if item.text:
                rows.append((item.section, item.text, item.evidence_type))
    for project in resume.projects:
        for text in [project.raw_text, *project.description]:
            if text:
                rows.append(("projects", text, "used"))
    for entry in resume.experience:
        texts = [entry.raw_text, entry.title, *entry.description]
        for text in texts:
            if text:
                rows.append(("experience", text, "used"))
    for entry in resume.certifications:
        if entry.raw_text or entry.name:
            rows.append(("certifications", entry.raw_text or entry.name or "", "mentioned"))
    return rows


def _phrase_evidence(resume: ResumeAnalysis, pattern: "re.Pattern[str]") -> List[SkillEvidence]:
    found: List[SkillEvidence] = []
    seen = set()
    for section, text, evidence_type in _resume_snippets(resume):
        masked = mask_contact_tokens(text)
        match = pattern.search(masked)
        if not match:
            continue
        snippet = _snippet(text, match)
        key = (section, snippet)
        if key in seen:
            continue
        seen.add(key)
        found.append(SkillEvidence(
            section=section, text=snippet, evidence_type=evidence_type, matched_as=match.group(),
        ))
    found.sort(key=lambda item: 0 if item.evidence_type == "used" else 1)
    return found[: config.MAX_EVIDENCE_PER_SKILL]


def _related_names(name: Optional[str], resume: ResumeAnalysis) -> List[str]:
    if not name:
        return []
    names = []
    for group in _RELATED_GROUPS:
        if name not in group:
            continue
        for skill in resume.skills:
            if skill.name in group and skill.name != name and skill.evidence:
                names.append(skill.name)
    return sorted(set(names))


def _matched_skill(requirement: JobRequirement, evidence: List[SkillEvidence], note: str) -> RequirementMatch:
    evidence_type = "used" if any(item.evidence_type == "used" for item in evidence) else "mentioned"
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MATCHED, evidence_type=evidence_type,
        evidence=evidence, support=[item.text for item in evidence], note=note,
    )


def _phrase_match(requirement: JobRequirement, resume: ResumeAnalysis, name: str) -> RequirementMatch:
    """Match the stated phrase. A nearby skill is not an exact match."""
    pattern = PHRASE_PATTERNS[name]
    evidence = _phrase_evidence(resume, pattern)
    if not evidence and name == "state management":
        redux = next((skill for skill in resume.skills if skill.name == "Redux" and skill.evidence), None)
        if redux is not None:
            evidence = list(redux.evidence)
            return _matched_skill(
                requirement, evidence,
                "The resume shows Redux, which is a state-management approach. Proficiency is not inferred.",
            )
        evidence = _phrase_evidence(resume, PHRASE_PATTERNS["Flux"])
        if evidence:
            return _matched_skill(
                requirement, evidence,
                "The resume states Flux, which the posting accepts as a state-management approach. "
                "Proficiency is not inferred.",
            )
    if evidence:
        kind = "uses" if any(item.evidence_type == "used" for item in evidence) else "mentions"
        return _matched_skill(
            requirement, evidence,
            f"The resume {kind} this requirement. Proficiency is not inferred.",
        )
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MISSING,
        note="The resume evidence does not include this requirement.",
    )


def _accepted_names(requirement: JobRequirement) -> List[str]:
    if requirement.alternatives:
        return list(requirement.alternatives)
    if requirement.skill_name:
        return [requirement.skill_name]
    return []


def _exact_named(name: str, requirement: JobRequirement, resume: ResumeAnalysis) -> Optional[RequirementMatch]:
    """A match with resume evidence, or None when this name is not exact."""
    if name in PHRASE_PATTERNS:
        phrase = _phrase_match(requirement, resume, name)
        if phrase.outcome == OUTCOME_MATCHED:
            return phrase
        return None
    detected = next((skill for skill in resume.skills if skill.name == name), None)
    if detected is None or not detected.evidence or detected.evidence_type not in ("used", "mentioned"):
        return None
    note = "The resume mentions this skill. Proficiency is not inferred."
    if detected.evidence_type == "used":
        note = "The resume uses this skill in experience or projects. Proficiency is not inferred."
    return _matched_skill(requirement, list(detected.evidence), note)


def _skill_match(requirement: JobRequirement, resume: ResumeAnalysis) -> RequirementMatch:
    names = _accepted_names(requirement)
    for name in names:
        exact = _exact_named(name, requirement, resume)
        if exact is not None:
            exact.satisfied_by = name
            if len(names) > 1:
                exact.note = (
                    f"The posting accepts {' or '.join(names)}. The resume shows {name}. "
                    "Proficiency is not inferred."
                )
            return exact
    if len(names) == 1:
        name = names[0]
        detected = next((skill for skill in resume.skills if skill.name == name), None)
        if detected is not None:
            return RequirementMatch(
                requirement=requirement, outcome=OUTCOME_MISSING,
                note="The skill was listed without a supporting resume line, so it is not counted as a match.",
            )
        related = _related_names(name, resume)
        if related:
            return RequirementMatch(
                requirement=requirement, outcome=OUTCOME_RELATED, related_skills=related,
                note="A different skill was found. Not an exact match.",
            )
    if len(names) > 1:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_MISSING,
            note=(
                f"The posting accepts {' or '.join(names)}. "
                "The resume evidence does not include any of them."
            ),
        )
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MISSING,
        note="The resume evidence does not include this skill.",
    )


def _degree_match(requirement: JobRequirement, resume: ResumeAnalysis) -> RequirementMatch:
    level_hits: List[EducationEntry] = []
    for entry in resume.education:
        if degree_level(entry.degree) == requirement.degree_level:
            level_hits.append(entry)
    if not level_hits:
        stated = [entry for entry in resume.education if entry.degree]
        if resume.education and not stated:
            return RequirementMatch(
                requirement=requirement, outcome=OUTCOME_INDETERMINATE,
                note="The resume has an education entry but no degree text to compare.",
            )
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_MISSING,
            note="No resume degree matches the stated level. A different level is not treated as a match.",
        )
    decisions = [_fields_match(requirement.degree_field, entry.field_of_study) for entry in level_hits]
    matched = [entry for entry, decision in zip(level_hits, decisions) if decision == "yes"]
    if matched:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_MATCHED,
            support=[_clip(entry.raw_text or entry.degree or "") for entry in matched],
            note="Matched on the stated degree level"
            + (" and field." if requirement.degree_field else ". The posting did not require a field."),
        )
    if "unknown" in decisions:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_INDETERMINATE,
            note="The resume states this degree level but not the field the posting asks for.",
        )
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MISSING,
        note="The resume degree level matches, but the stated field does not.",
    )


def _certification_match(requirement: JobRequirement, resume: ResumeAnalysis) -> RequirementMatch:
    named = [entry for entry in resume.certifications if entry.name]
    matched = [
        entry for entry in named
        if _certs_match(requirement.certification_name or "", entry.name or "")
    ]
    if matched:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_MATCHED,
            support=[_clip(entry.raw_text or entry.name or "") for entry in matched],
            note="The certification name on the resume contains the name stated in the posting.",
        )
    if resume.certifications and not named:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_INDETERMINATE,
            note="The resume has a certification entry but no name to compare.",
        )
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MISSING,
        note="No resume certification name matches the posting.",
    )


def _entry_blob(entry: ExperienceEntry) -> str:
    parts = [entry.raw_text, entry.title, entry.organization, *entry.description]
    return "\n".join(part for part in parts if part)


def _mentions_focus(entry: ExperienceEntry, focus: str) -> bool:
    return re.search(
        r"(?<![A-Za-z0-9])" + re.escape(focus) + r"(?![A-Za-z0-9])",
        _entry_blob(entry),
        re.IGNORECASE,
    ) is not None


def _dated_entries(entries: List[ExperienceEntry], as_of: date) -> Tuple[List[Tuple[float, ExperienceEntry]], bool]:
    spans: List[Tuple[float, ExperienceEntry]] = []
    undated = False
    for entry in entries:
        years = _duration_years(entry, as_of)
        if years is None:
            undated = True
        else:
            spans.append((years, entry))
    return spans, undated


def _experience_match(requirement: JobRequirement, resume: ResumeAnalysis, as_of: date) -> RequirementMatch:
    if requirement.experience_status != EXPERIENCE_STATED or requirement.years_min is None:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_INDETERMINATE,
            note=requirement.note or "The posting does not state a number of years.",
        )
    focus = requirement.experience_focus
    entries = resume.experience
    if focus:
        entries = [entry for entry in resume.experience if _mentions_focus(entry, focus)]
        if not entries:
            return RequirementMatch(
                requirement=requirement, outcome=OUTCOME_INDETERMINATE,
                note=(
                    f"The posting asks for {requirement.years_min:g} years with {focus}, "
                    "but the resume has no dated employment that mentions it. "
                    "This duration is unverified and is not counted as satisfied or failed. "
                    "Project mentions are not treated as professional experience."
                ),
            )
    spans, undated = _dated_entries(entries, as_of)
    if not spans:
        if entries:
            note = (
                "Experience entries do not include an explicit start and end date, so the duration is unverified. "
                "It is not counted as satisfied or failed."
            )
        else:
            note = (
                "The resume does not state employment dates, so this duration is unverified. "
                "It is not counted as satisfied or failed. "
                "Project mentions are not treated as professional experience."
            )
        return RequirementMatch(requirement=requirement, outcome=OUTCOME_INDETERMINATE, note=note)

    total = sum(years for years, _entry in spans)
    support = [_clip(entry.raw_text or f"{entry.start_date} - {entry.end_date}") for _years, entry in spans]
    minimum = requirement.years_min
    scope = f" mentioning {focus}" if focus else ""
    if undated and total < minimum:
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_INDETERMINATE, support=support,
            note=(
                f"Dated experience{scope} adds up to {total:.1f} years, below the stated {minimum:g} years, "
                "and other experience has no explicit dates, so this duration is unverified. "
                "It is not counted as satisfied or failed."
            ),
        )
    if total >= minimum:
        extra = " Undated experience was not added." if undated else ""
        return RequirementMatch(
            requirement=requirement, outcome=OUTCOME_MATCHED, support=support,
            note=(
                f"Dated experience{scope} adds up to {total:.1f} years, which meets the stated {minimum:g} years. "
                "Overlapping dates were not removed." + extra
            ),
        )
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_MISSING, support=support,
        note=(
            f"Dated experience{scope} adds up to {total:.1f} years, below the stated {minimum:g} years. "
            "Overlapping dates were not removed."
        ),
    )


def _compare_one(requirement: JobRequirement, resume: ResumeAnalysis, as_of: date) -> RequirementMatch:
    if requirement.kind == REQUIREMENT_SKILL:
        return _skill_match(requirement, resume)
    if requirement.kind == REQUIREMENT_DEGREE:
        return _degree_match(requirement, resume)
    if requirement.kind == REQUIREMENT_CERTIFICATION:
        return _certification_match(requirement, resume)
    if requirement.kind == REQUIREMENT_EXPERIENCE:
        return _experience_match(requirement, resume, as_of)
    return RequirementMatch(
        requirement=requirement, outcome=OUTCOME_INDETERMINATE,
        note="This requirement kind is not compared.",
    )


def _guard(match: RequirementMatch) -> RequirementMatch:
    """A match without resume support is not reported as matched."""
    if match.outcome != OUTCOME_MATCHED:
        if match.outcome == OUTCOME_RELATED:
            match.evidence = []
            match.evidence_type = None
        return match
    has_skill_evidence = bool(match.evidence)
    has_support = bool(match.support)
    if not has_skill_evidence and not has_support:
        match.outcome = OUTCOME_MISSING
        match.evidence_type = None
        match.note = "No supporting resume line was available, so this is not counted as a match."
    return match


def compare_requirements(
    resume: ResumeAnalysis,
    job: JobAnalysis,
    *,
    as_of: Optional[date] = None,
) -> MatchReport:
    """Compare each requirement. Related skills are never included in the match count."""
    if not isinstance(resume, ResumeAnalysis) or not isinstance(job, JobAnalysis):
        reason = "compare expects a ResumeAnalysis and a JobAnalysis."
        return MatchReport(status=STATUS_FAILED, reason=reason, errors=[reason])
    if as_of is not None and not isinstance(as_of, date):
        reason = "as_of must be a date."
        return MatchReport(status=STATUS_FAILED, reason=reason, errors=[reason])
    if job.status in _STOP_STATUSES:
        reason = job.reason or "The job description could not be read, so nothing was compared."
        return MatchReport(status=job.status, reason=reason, warnings=list(job.warnings), errors=list(job.errors))
    if resume.status in _STOP_STATUSES:
        reason = "The resume could not be read, so requirements were not compared."
        return MatchReport(status=resume.status, reason=reason, warnings=list(resume.warnings), errors=list(resume.errors))
    if not job.requirements:
        reason = job.reason or "No requirements could be identified."
        return MatchReport(status=job.status, reason=reason, warnings=list(job.warnings))

    today = as_of or date.today()
    matches = [_guard(_compare_one(requirement, resume, today)) for requirement in job.requirements]
    warnings = list(job.warnings)
    if any(item.requirement.kind == REQUIREMENT_EXPERIENCE for item in matches):
        warnings.append(_DURATION_WARNING)
    return MatchReport(status=STATUS_SUCCESS, matches=matches, warnings=warnings)
