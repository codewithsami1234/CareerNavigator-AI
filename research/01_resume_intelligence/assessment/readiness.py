"""Transparent readiness estimate from a finished comparison.

The number is an evidence-based estimate from the weights in ``config``. It is
not a trained model, not a prediction of hiring, and not an ATS score. It is
calculated only when a job comparison produced required items that can be scored.
Preferred requirements, unspecified requirements, and unverified durations are
reported and left out of the denominator. Public GitHub observations are
listed separately and do not change the number.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import config
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED,
    PRIORITY_PREFERRED, PRIORITY_REQUIRED, PRIORITY_UNSPECIFIED, STATUS_PARTIAL, STATUS_SUCCESS,
    JobAnalysis, MatchReport,
    ResumeAnalysis,
)

DISCLAIMER = (
    "This is an evidence-based estimate from a fixed rubric. "
    "It is not a validated prediction of hiring and it is not an ATS score."
)
_NO_JOB = "No job description was supplied, so job-specific readiness was not calculated."


@dataclass
class Criterion:
    name: str
    kind: str
    priority: str
    status: str
    scored: bool
    credit: float
    posting_text: str
    resume_evidence: List[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class ReadinessAssessment:
    status: str
    job_specific: bool
    estimate: Optional[int]
    band: str
    classification: str
    summary: str
    disclaimer: str
    criteria: List[Criterion] = field(default_factory=list)
    github_observations: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _band(estimate: Optional[int]) -> str:
    if estimate is None:
        return "not assessed"
    if estimate >= 85:
        return "strong evidence"
    if estimate >= 60:
        return "partial evidence"
    if estimate >= 30:
        return "limited evidence"
    return "little evidence"


def _criterion_name(requirement) -> str:
    """Experience keeps the word experience so a duration is not shown as a skill."""
    if requirement.kind == "experience":
        if requirement.years_min is not None and requirement.years_max is not None:
            label = f"{requirement.years_min:g}–{requirement.years_max:g} years of experience"
        elif requirement.years_min is not None:
            label = f"{requirement.years_min:g} years of experience"
        else:
            label = "experience"
        if requirement.experience_focus:
            return f"{label} with {requirement.experience_focus}"
        return label
    names = requirement.alternatives or [requirement.skill_name or requirement.kind]
    return " or ".join(name for name in names if name)


def _status_for(outcome: str) -> str:
    if outcome == OUTCOME_MATCHED:
        return "supported"
    if outcome == OUTCOME_RELATED:
        return "insufficient"
    if outcome == OUTCOME_MISSING:
        return "missing"
    return "unverified"


def _evidence_lines(match) -> List[str]:
    lines = [item.text for item in match.evidence if getattr(item, "text", None)]
    lines.extend(line for line in match.support if line)
    return lines


def _github_names(github) -> List[str]:
    if github is None or getattr(github, "status", None) != STATUS_SUCCESS:
        return []
    return sorted({item.skill_name for item in getattr(github, "skills", []) if item.skill_name})


def assess_readiness(
    resume: Optional[ResumeAnalysis],
    job: Optional[JobAnalysis],
    report: Optional[MatchReport],
    github=None,
) -> ReadinessAssessment:
    """Score required comparison outcomes. ``resume`` is accepted for provenance checks."""
    limitations = [
        DISCLAIMER,
        "Preferred and unspecified requirements are shown and are not part of the estimate.",
        "Unverified experience is shown and is not treated as a failed requirement.",
        "Related skills earn no credit.",
        "Public repository observations do not change the estimate.",
        "Overlapping dated jobs can inflate a generic experience total inside the comparison.",
    ]
    if resume is None or resume.status not in {STATUS_SUCCESS, STATUS_PARTIAL}:
        reason = "The resume could not be used, so readiness was not calculated."
        return ReadinessAssessment(
            status="unavailable", job_specific=False, estimate=None, band="not assessed",
            classification="not assessed", summary=reason, disclaimer=DISCLAIMER, limitations=limitations,
        )
    if job is None or report is None or report.status != STATUS_SUCCESS:
        if job is None:
            summary = _NO_JOB
        else:
            summary = (report.reason if report is not None and report.reason else None) or (
                "The job comparison did not succeed, so job-specific readiness was not calculated."
            )
        return ReadinessAssessment(
            status=STATUS_SUCCESS, job_specific=False, estimate=None, band="not assessed",
            classification="not assessed", summary=summary, disclaimer=DISCLAIMER, limitations=limitations,
        )

    observed = _github_names(github)
    criteria: List[Criterion] = []
    observations: List[str] = []
    earned = 0.0
    scored = 0
    for match in report.matches:
        requirement = match.requirement
        names = requirement.alternatives or [requirement.skill_name or requirement.kind]
        label = _criterion_name(requirement)
        outcome_status = _status_for(match.outcome)
        is_required = requirement.priority == PRIORITY_REQUIRED
        unverified = match.outcome == OUTCOME_INDETERMINATE
        include_in_score = is_required and not unverified
        credit = config.READINESS_MATCHED_CREDIT if match.outcome == OUTCOME_MATCHED else config.READINESS_UNSATISFIED_CREDIT
        if include_in_score:
            scored += 1
            earned += credit
        detail = match.note or ""
        if requirement.kind == "skill" and outcome_status == "missing":
            overlap = [name for name in names if name in observed]
            if overlap:
                note = (
                    f"Also observed in a public repository: {', '.join(overlap)}. "
                    "That observation does not change this estimate."
                )
                observations.append(f"{label}: {note}")
                detail = (detail + " " + note).strip()
        criteria.append(Criterion(
            name=label,
            kind=requirement.kind,
            priority=requirement.priority,
            status=outcome_status,
            scored=include_in_score,
            credit=credit if include_in_score else 0.0,
            posting_text=requirement.text,
            resume_evidence=_evidence_lines(match) if match.outcome == OUTCOME_MATCHED else [],
            detail=detail,
        ))

    if github is not None and getattr(github, "status", None) not in (None, STATUS_SUCCESS):
        limitations.append("GitHub analysis was not available, so repository observations were not added.")

    unverified_required = sum(
        1 for item in criteria
        if item.priority == PRIORITY_REQUIRED and item.status == "unverified"
    )
    preferred_count = sum(1 for item in criteria if item.priority == PRIORITY_PREFERRED)
    unspecified_count = sum(1 for item in criteria if item.priority == PRIORITY_UNSPECIFIED)
    required_count = sum(1 for item in criteria if item.priority == PRIORITY_REQUIRED)
    exclusion = (
        f"The denominator is {scored} required item(s). "
        f"{unverified_required} unverified required item(s), {preferred_count} preferred item(s), "
        f"and {unspecified_count} unspecified item(s) are shown and are not in the denominator."
    )
    if scored == 0:
        estimate = None
        if required_count == 0:
            summary = (
                "No numeric estimate is available because the posting did not label any requirement as required. "
                "Unspecified items stay unspecified and are not treated as required failures. "
                + exclusion
            )
        else:
            summary = (
                "No required item could be scored. Unverified and non-required items "
                "were not treated as failures. " + exclusion
            )
    else:
        estimate = int(round(100 * earned / scored))
        matched_scored = sum(1 for item in criteria if item.scored and item.status == "supported")
        summary = (
            f"Estimate {estimate} out of 100. "
            f"{matched_scored} matched and {scored - matched_scored} unsatisfied required item(s) were scored. "
            f"{exclusion} "
            f"A matched required item contributes {config.READINESS_MATCHED_CREDIT:g}; "
            f"a related or missing required item contributes {config.READINESS_UNSATISFIED_CREDIT:g}."
        )
    band = _band(estimate)
    return ReadinessAssessment(
        status=STATUS_SUCCESS,
        job_specific=True,
        estimate=estimate,
        band=band,
        classification=band,
        summary=summary,
        disclaimer=DISCLAIMER,
        criteria=criteria,
        github_observations=observations,
        limitations=limitations,
    )
