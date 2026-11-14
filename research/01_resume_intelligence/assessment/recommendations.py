"""Skill-gap recommendations taken from a comparison report.

This module does not parse resumes or match skills again. It does not invent
courses, certificates, or URLs, and it does not tell the user to claim a skill
they have not demonstrated.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from assessment.prerequisites import prerequisites_for, sequence_rank
from schemas import (
    OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED, PRIORITY_PREFERRED, PRIORITY_REQUIRED,
    PRIORITY_UNSPECIFIED,
    REQUIREMENT_EXPERIENCE, REQUIREMENT_SKILL, JobAnalysis, MatchReport, STATUS_SUCCESS,
)

_UNAVAILABLE = "No job description was supplied, so no role-specific gaps were calculated."


@dataclass
class Recommendation:
    skill_name: str
    priority: str
    gap_kind: str
    reason: str
    posting_text: str
    prerequisites: List[str] = field(default_factory=list)
    practice_task: str = ""
    evidence_note: Optional[str] = None


@dataclass
class RecommendationReport:
    status: str = "unavailable"
    reason: Optional[str] = None
    items: List[Recommendation] = field(default_factory=list)
    experience_gaps: List[Recommendation] = field(default_factory=list)
    matched_skills: List[str] = field(default_factory=list)
    shown_skills: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _practice(skill_name: str) -> str:
    return (
        f"Build a small project that uses {skill_name} for a concrete task, and keep the code "
        f"or a short write-up as evidence. Do not add {skill_name} to a resume until that work exists."
    )


def _limitations() -> List[str]:
    return [
        "Recommendations come from the comparison outcomes. They are not a hiring judgment.",
        "Prerequisite links are a local sequencing map, not a measured curriculum.",
        "No course links or certificates are suggested.",
        "A skill named on a resume is not treated as proof of proficiency.",
        "Do not add a skill or a length of employment to a resume until the evidence exists.",
    ]


def _accepted(requirement) -> List[str]:
    if requirement.alternatives:
        return [name for name in requirement.alternatives if name]
    if requirement.skill_name:
        return [requirement.skill_name]
    return []


def _covers(item: Recommendation) -> set:
    return {part.strip() for part in item.skill_name.split(" or ") if part.strip()}


def recommend_gaps(
    job: Optional[JobAnalysis],
    report: Optional[MatchReport],
    evidenced_skills: Optional[List[str]] = None,
) -> RecommendationReport:
    """Order missing required skills ahead of preferred ones."""
    if job is None or report is None:
        return RecommendationReport(status="unavailable", reason=_UNAVAILABLE, limitations=_limitations())
    if report.status != STATUS_SUCCESS or not report.matches:
        reason = report.reason or job.reason or "No comparison was available, so no gaps were calculated."
        return RecommendationReport(status="unavailable", reason=reason, limitations=_limitations())

    matched: List[str] = []
    for item in report.matches:
        if item.outcome != OUTCOME_MATCHED or item.requirement.kind != REQUIREMENT_SKILL:
            continue
        shown = item.satisfied_by
        if not shown and not item.requirement.alternatives:
            shown = item.requirement.skill_name
        if shown and shown not in matched:
            matched.append(shown)
    matched_set = set(matched)
    shown = []
    for name in evidenced_skills or []:
        if name and name not in shown:
            shown.append(name)
    known = matched_set | set(shown)

    skill_items: List[Recommendation] = []
    experience_items: List[Recommendation] = []
    for match in report.matches:
        requirement = match.requirement
        if requirement.kind == REQUIREMENT_EXPERIENCE and match.outcome != OUTCOME_MATCHED:
            label = requirement.experience_focus or "professional experience"
            if match.outcome == OUTCOME_MISSING:
                gap_kind = "short_experience"
                reason = (
                    "Dated employment is shorter than the length the posting states. "
                    "Project mentions are not professional employment. "
                    "Do not add this length to a resume until the dated employment exists."
                )
            else:
                gap_kind = "unverified_experience"
                reason = (
                    "The resume does not include enough dated employment to verify this length. "
                    "It is not counted as satisfied or failed. "
                    "Project mentions are not professional employment. "
                    "Do not add this length to a resume until the dated employment exists."
                )
            experience_items.append(Recommendation(
                skill_name=label,
                priority=requirement.priority,
                gap_kind=gap_kind,
                reason=reason,
                posting_text=requirement.text,
                practice_task=(
                    "Collect dated employment records that state this work. "
                    "Do not present a project as years of professional employment."
                ),
                evidence_note=match.note,
            ))
            continue
        if requirement.kind != REQUIREMENT_SKILL or requirement.priority not in (
            PRIORITY_REQUIRED, PRIORITY_PREFERRED, PRIORITY_UNSPECIFIED,
        ):
            continue
        if match.outcome == OUTCOME_MATCHED:
            continue
        names = [name for name in _accepted(requirement) if name not in matched_set]
        if not names:
            continue
        if match.outcome == OUTCOME_MISSING:
            if requirement.priority == PRIORITY_REQUIRED:
                gap_kind = "missing_required"
            elif requirement.priority == PRIORITY_PREFERRED:
                gap_kind = "missing_preferred"
            else:
                gap_kind = "missing_unspecified"
        elif match.outcome == OUTCOME_RELATED:
            gap_kind = "related"
        else:
            continue
        related_note = None
        if match.related_skills:
            related_note = "Related, not a match: " + ", ".join(match.related_skills)
        if len(requirement.alternatives) > 1:
            label = " or ".join(requirement.alternatives)
            prereqs: List[str] = []
            for name in requirement.alternatives:
                for prereq in prerequisites_for(name):
                    if prereq not in known and prereq not in prereqs and prereq not in requirement.alternatives:
                        prereqs.append(prereq)
            if requirement.priority == PRIORITY_UNSPECIFIED:
                acceptance = f"The posting names {label} and does not label it required or preferred."
            else:
                acceptance = f"The posting accepts {label}. The resume does not show any of them."
            skill_items.append(Recommendation(
                skill_name=label,
                priority=requirement.priority,
                gap_kind=gap_kind,
                reason=f"{acceptance} {requirement.text}".strip(),
                posting_text=requirement.text,
                prerequisites=prereqs,
                practice_task=(
                    f"Build a small project that uses one of: {label}. Keep the code or a short write-up "
                    "as evidence. Do not add any of these to a resume until that work exists."
                ),
                evidence_note=related_note or match.note,
            ))
            continue
        name = names[0]
        prereqs = [item for item in prerequisites_for(name) if item not in known]
        if requirement.priority == PRIORITY_UNSPECIFIED:
            reason = (
                f"The posting names {name} and does not label it required or preferred. "
                f"{requirement.text}"
            ).strip()
        else:
            reason = f"The posting asks for {name}. {requirement.text}".strip()
        skill_items.append(Recommendation(
            skill_name=name,
            priority=requirement.priority,
            gap_kind=gap_kind,
            reason=reason,
            posting_text=requirement.text,
            prerequisites=prereqs,
            practice_task=_practice(name),
            evidence_note=related_note or match.note,
        ))

    rank = {"missing_required": 0, "missing_preferred": 1, "missing_unspecified": 2, "related": 3}
    skill_items.sort(key=lambda item: (
        rank.get(item.gap_kind, 9), sequence_rank(item.skill_name), item.skill_name.lower(),
    ))
    deduped: List[Recommendation] = []
    seen_names = set()
    for item in skill_items:
        if item.skill_name in seen_names:
            continue
        seen_names.add(item.skill_name)
        deduped.append(item)
    kept: List[Recommendation] = []
    for item in deduped:
        covered = _covers(item)
        if any(covered < _covers(other) for other in deduped):
            continue
        kept.append(item)
    return RecommendationReport(
        status=STATUS_SUCCESS,
        items=kept,
        experience_gaps=experience_items,
        matched_skills=sorted(matched_set),
        shown_skills=shown,
        limitations=_limitations(),
    )
