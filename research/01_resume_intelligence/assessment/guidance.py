"""Explanations built only from a finished resume, comparison, and roadmap.

This module does not parse files, does not rescore readiness, and does not
invent courses or qualifications. A mention stays a mention. A related skill
stays unmatched. Career-path labels only name categories that already contain
extracted skills.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from schemas import (
    OUTCOME_MATCHED, OUTCOME_RELATED, REQUIREMENT_SKILL, STATUS_PARTIAL, STATUS_SUCCESS,
)

# A path is emitted only when the resume already has this many supporting
# skills, including at least one skill in ``required_categories`` when that
# tuple is non-empty. Job text alone cannot create a path.
_PATHS: Tuple[Tuple[str, Tuple[str, ...], Tuple[str, ...], int], ...] = (
    ("Software engineering", ("Programming Languages", "Backend Development", "Development Tools"), ("Programming Languages",), 2),
    ("Web development", ("Frontend and Web Development", "Programming Languages"), ("Frontend and Web Development",), 2),
    ("Data and machine learning", ("AI and Machine Learning", "Data Science", "NLP", "Computer Vision"), (), 2),
    ("Cloud and DevOps", ("Cloud and DevOps",), (), 2),
    ("Cybersecurity", ("Cybersecurity",), (), 2),
    ("Game development", ("Game Development",), (), 2),
)
_SHORT_TERM = {"prerequisite", "missing_required"}
_MENTION_LIMIT = 8


@dataclass
class GuidanceItem:
    title: str
    kind: str
    reason: str
    evidence: List[str] = field(default_factory=list)
    priority: Optional[str] = None
    source: str = "comparison"


@dataclass
class CareerGuidance:
    status: str = "unavailable"
    reason: Optional[str] = None
    skills_to_strengthen: List[GuidanceItem] = field(default_factory=list)
    partially_supported: List[GuidanceItem] = field(default_factory=list)
    project_ideas: List[GuidanceItem] = field(default_factory=list)
    career_paths: List[GuidanceItem] = field(default_factory=list)
    short_term: List[GuidanceItem] = field(default_factory=list)
    long_term: List[GuidanceItem] = field(default_factory=list)
    weekly_focus: List[GuidanceItem] = field(default_factory=list)
    github_notes: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _limitations() -> List[str]:
    return [
        "Guidance restates resume evidence, comparison outcomes, and the existing roadmap. It does not add a score.",
        "A mention-only match still counts in the readiness estimate. Calling it partial support does not change that number.",
        "Related skills do not satisfy a requirement and do not earn credit.",
        "Career-path labels are not job offers.",
        "Focus slots follow roadmap order. They are not a measured study duration.",
        "GitHub metadata is not resume evidence and is not used to choose a path.",
    ]


def _positive_hours(weekly_hours: Optional[int]) -> Optional[int]:
    if isinstance(weekly_hours, bool) or not isinstance(weekly_hours, int) or weekly_hours <= 0:
        return None
    return weekly_hours


def _requirement_label(requirement) -> str:
    if getattr(requirement, "skill_name", None):
        return requirement.skill_name
    alternatives = [name for name in (getattr(requirement, "alternatives", None) or []) if name]
    if alternatives:
        return " or ".join(alternatives)
    return getattr(requirement, "text", None) or getattr(requirement, "kind", None) or "Requirement"


def _evidence_lines(match) -> List[str]:
    lines = []
    for item in getattr(match, "evidence", None) or []:
        text = getattr(item, "text", None)
        if text and text not in lines:
            lines.append(text)
    return lines


def _usable(resume) -> bool:
    return resume is not None and getattr(resume, "status", None) in {STATUS_SUCCESS, STATUS_PARTIAL}


def _skills_by_category(resume) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for skill in getattr(resume, "skills", None) or []:
        name = getattr(skill, "name", None)
        if not name or not getattr(skill, "evidence", None):
            continue
        category = getattr(skill, "category", None) or "Uncategorised"
        names = grouped.setdefault(category, [])
        if name not in names:
            names.append(name)
    return grouped


def _career_paths(resume) -> List[GuidanceItem]:
    grouped = _skills_by_category(resume)
    ranked = []
    for title, categories, required, minimum in _PATHS:
        if required and not any(grouped.get(category) for category in required):
            continue
        names: List[str] = []
        used_categories: List[str] = []
        for category in categories:
            for name in grouped.get(category, []):
                if name not in names:
                    names.append(name)
            if grouped.get(category):
                used_categories.append(category)
        if len(names) < minimum:
            continue
        ranked.append((len(names), title, names, used_categories))
    ranked.sort(key=lambda row: (-row[0], row[1].lower()))
    items = []
    for _count, title, names, categories in ranked:
        items.append(GuidanceItem(
            title=title,
            kind="career_path",
            reason=(
                f"Suggested because the resume shows {', '.join(names)} "
                f"under {', '.join(categories)}. "
                "This label groups those extracted skills. It is not a job offer and it is not a prediction."
            ),
            evidence=list(names),
            source="resume",
        ))
    return items


def _mention_only_from_resume(resume) -> List[GuidanceItem]:
    items = []
    for skill in getattr(resume, "skills", None) or []:
        if getattr(skill, "evidence_type", None) != "mentioned" or not getattr(skill, "evidence", None):
            continue
        sections = []
        snippets = []
        for item in skill.evidence:
            if item.section and item.section not in sections:
                sections.append(item.section)
            if item.text and item.text not in snippets:
                snippets.append(item.text)
        where = ", ".join(sections) if sections else "the resume"
        items.append(GuidanceItem(
            title=skill.name,
            kind="strengthen",
            reason=(
                f"{skill.name} appears as a mention in {where}, not in Experience or Projects. "
                "That is not a proficiency level. Practice it before describing it as hands-on."
            ),
            evidence=snippets,
            source="resume",
        ))
    items.sort(key=lambda item: item.title.lower())
    return items


def _from_comparison(comparison) -> Tuple[List[GuidanceItem], List[GuidanceItem]]:
    partial: List[GuidanceItem] = []
    strengthen: List[GuidanceItem] = []
    if comparison is None or getattr(comparison, "status", None) != STATUS_SUCCESS:
        return partial, strengthen
    for match in getattr(comparison, "matches", None) or []:
        requirement = match.requirement
        if getattr(requirement, "kind", None) != REQUIREMENT_SKILL:
            continue
        label = _requirement_label(requirement)
        snippets = _evidence_lines(match)
        if match.outcome == OUTCOME_MATCHED and match.evidence_type == "mentioned":
            partial.append(GuidanceItem(
                title=label,
                kind="partial",
                reason=(
                    f"The comparison marks {label} as matched because the resume mentions it. "
                    "The supporting lines are not in Experience or Projects, so this is partial support, "
                    "not demonstrated use. It still counts as a match in the readiness estimate."
                ),
                evidence=snippets,
                priority=requirement.priority,
                source="resume",
            ))
            quote = f" Resume line: {snippets[0]}" if snippets else ""
            strengthen.append(GuidanceItem(
                title=label,
                kind="strengthen",
                reason=(
                    f"{label} is matched from a mention only. "
                    "Practice it in a project or a dated role before describing it as hands-on."
                    + quote
                ),
                evidence=snippets,
                priority=requirement.priority,
                source="resume",
            ))
        elif match.outcome == OUTCOME_RELATED:
            related = ", ".join(match.related_skills) if match.related_skills else "a related skill"
            partial.append(GuidanceItem(
                title=label,
                kind="partial",
                reason=(
                    f"The resume shows {related}, which the comparison treats as related to {label}. "
                    "Related skills do not satisfy the requirement and do not earn readiness credit."
                ),
                evidence=list(match.related_skills or []),
                priority=requirement.priority,
                source="comparison",
            ))
    return partial, strengthen


def _project_ideas(recommendations, strengthen: Sequence[GuidanceItem]) -> List[GuidanceItem]:
    ideas: List[GuidanceItem] = []
    seen = set()
    items = []
    if recommendations is not None and getattr(recommendations, "status", None) == STATUS_SUCCESS:
        items.extend(getattr(recommendations, "items", None) or [])
    for item in items:
        title = getattr(item, "skill_name", None) or ""
        practice = getattr(item, "practice_task", None) or ""
        if not title or not practice or title in seen:
            continue
        seen.add(title)
        posting = getattr(item, "posting_text", None) or ""
        ideas.append(GuidanceItem(
            title=title,
            kind="project",
            reason=f"{item.reason} Project idea: {practice}",
            evidence=[posting] if posting else [],
            priority=getattr(item, "priority", None),
            source="job",
        ))
    for item in strengthen:
        if item.title in seen:
            continue
        seen.add(item.title)
        ideas.append(GuidanceItem(
            title=item.title,
            kind="project",
            reason=(
                f"{item.reason} Project idea: build a small project that uses {item.title} "
                "for a concrete task, and keep the code or a short write-up as evidence. "
                f"Do not add a stronger claim about {item.title} until that work exists."
            ),
            evidence=list(item.evidence),
            priority=item.priority,
            source="resume",
        ))
    return ideas


def _horizons(roadmap) -> Tuple[List[GuidanceItem], List[GuidanceItem]]:
    short_term: List[GuidanceItem] = []
    long_term: List[GuidanceItem] = []
    if roadmap is None or getattr(roadmap, "status", None) != STATUS_SUCCESS:
        return short_term, long_term
    for item in getattr(roadmap, "milestones", None) or []:
        kind = "short_term" if item.kind in _SHORT_TERM else "long_term"
        row = GuidanceItem(
            title=item.title,
            kind=kind,
            reason=item.objective,
            evidence=[item.posting_text] if item.posting_text else [],
            priority=item.kind,
            source="roadmap",
        )
        if kind == "short_term":
            short_term.append(row)
        else:
            long_term.append(row)
    return short_term, long_term


def _weekly(roadmap, weekly_hours: Optional[int]) -> List[GuidanceItem]:
    hours = _positive_hours(weekly_hours)
    milestones = []
    if roadmap is not None and getattr(roadmap, "status", None) == STATUS_SUCCESS:
        milestones = list(getattr(roadmap, "milestones", None) or [])
    if hours is None or not milestones:
        return []
    total = len(milestones)
    slots = []
    for index, item in enumerate(milestones, start=1):
        slots.append(GuidanceItem(
            title=item.title,
            kind="weekly",
            reason=(
                f"Sequence slot {index} of {total}. "
                f"If you use the {hours} hours you entered, work on this before later slots. "
                "This slot is ordering, not an estimate of how long the skill takes."
            ),
            evidence=[item.objective] if item.objective else [],
            priority=item.kind,
            source="roadmap",
        ))
    return slots


def _github_notes(github) -> List[str]:
    if github is None:
        return []
    status = getattr(github, "status", None)
    if status != STATUS_SUCCESS:
        return ["GitHub evidence was unavailable, so it was not used."]
    names = []
    for skill in getattr(github, "skills", None) or []:
        name = getattr(skill, "skill_name", None)
        if name and name not in names:
            names.append(name)
    if not names:
        return [
            "The public profile was read. No taxonomy skills were observed in the scanned metadata, "
            "so GitHub did not add career-path evidence. Source code was not inspected."
        ]
    return [
        "Public GitHub metadata named "
        + ", ".join(names)
        + ". That list is not resume evidence and was not used to choose a career path. "
        "Source code was not inspected."
    ]


def build_guidance(
    resume,
    job=None,
    comparison=None,
    recommendations=None,
    roadmap=None,
    github=None,
    *,
    weekly_hours: Optional[int] = None,
) -> CareerGuidance:
    """Explain gaps and paths from objects the pipeline already produced."""
    limitations = _limitations()
    if not _usable(resume):
        return CareerGuidance(
            status="unavailable",
            reason="The resume could not be used, so guidance was not generated.",
            limitations=limitations,
        )

    paths = _career_paths(resume)
    if not paths:
        limitations.append("No career-path label met the category minimum, so none was suggested.")
    partial, strengthen = _from_comparison(comparison)
    compared = comparison is not None and getattr(comparison, "status", None) == STATUS_SUCCESS
    if not compared:
        mention_only = _mention_only_from_resume(resume)
        if len(mention_only) > _MENTION_LIMIT:
            limitations.append(
                "Only the first 8 mention-only skills are listed when no job comparison is available."
            )
            mention_only = mention_only[:_MENTION_LIMIT]
        strengthen = mention_only
        limitations.append(
            "No job was compared, so skills to strengthen are resume skills that were only mentioned, "
            "not used in experience or projects."
        )
    elif not strengthen:
        limitations.append(
            "No matched skill was supported only by a mention, so none was listed to strengthen."
        )
    projects = _project_ideas(recommendations, strengthen)
    short_term, long_term = _horizons(roadmap)
    weekly = _weekly(roadmap, weekly_hours)
    if not weekly:
        if _positive_hours(weekly_hours) is None:
            limitations.append("No positive weekly hour budget was supplied, so milestones were not placed in focus slots.")
        else:
            limitations.append("No roadmap milestones were available, so no focus slots were created.")
    produced = any((paths, partial, strengthen, projects, short_term, long_term, weekly))
    return CareerGuidance(
        status=STATUS_SUCCESS,
        reason=None if produced else "The resume did not contain enough categorized skills or job gaps to add further guidance.",
        skills_to_strengthen=strengthen,
        partially_supported=partial,
        project_ideas=projects,
        career_paths=paths,
        short_term=short_term,
        long_term=long_term,
        weekly_focus=weekly,
        github_notes=_github_notes(github),
        limitations=limitations,
    )
