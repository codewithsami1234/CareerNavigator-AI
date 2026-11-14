"""Turn a pipeline result into display rows. Missing values stay missing."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import config
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED,
    STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_PARTIAL, STATUS_SUCCESS,
    JobAnalysis, JobRequirement, MatchReport, ResumeAnalysis,
)


def detected_section_names(analysis: ResumeAnalysis) -> List[str]:
    return [section.name for section in analysis.sections if section.name != "header"]


def contact_fields(analysis: ResumeAnalysis) -> List[Tuple[str, str]]:
    contact = analysis.contact
    pairs = (
        ("Name", contact.name),
        ("Email", contact.email),
        ("Phone", contact.phone),
        ("Location", contact.location),
        ("LinkedIn", contact.linkedin),
        ("GitHub", contact.github),
        ("LeetCode", getattr(contact, "leetcode", None)),
        ("X (Twitter)", getattr(contact, "twitter", None)),
    )
    return [(label, value) for label, value in pairs if value]


def missing_contact_labels(analysis: ResumeAnalysis) -> List[str]:
    present = {label for label, _value in contact_fields(analysis)}
    return [label for label in ("Name", "Email", "Phone", "Location", "LinkedIn", "GitHub") if label not in present]


def skill_rows(analysis: ResumeAnalysis) -> List[Tuple[str, str, str, int]]:
    """Name, category, evidence type, mention count. No proficiency."""
    return [
        (skill.name, skill.category, skill.evidence_type, skill.mention_count)
        for skill in analysis.skills
    ]


def _year_span(start, end, ongoing, graduation) -> str:
    parts: List[str] = []
    if start:
        parts.append(str(start))
    if ongoing and end:
        parts.append(f"{end} (ongoing)")
    elif end:
        parts.append(str(end))
    elif ongoing:
        parts.append("ongoing")
    text = " – ".join(parts)
    if graduation and graduation != end:
        graduated = f"graduated {graduation}"
        text = f"{text}; {graduated}" if text else graduated
    return text


def education_entries(analysis: ResumeAnalysis) -> List[List[str]]:
    rows = []
    for entry in analysis.education:
        lines = []
        title = " — ".join(part for part in (entry.degree, entry.field_of_study) if part)
        if title:
            lines.append(title)
        if entry.institution:
            lines.append(entry.institution)
        span = _year_span(entry.start_year, entry.end_year, entry.ongoing, entry.graduation_year)
        if span:
            lines.append(span)
        if entry.gpa:
            lines.append(f"GPA {entry.gpa}")
        if not lines and entry.raw_text.strip():
            lines.append(entry.raw_text.strip())
        rows.append(lines or ["An education entry was returned without structured fields."])
    return rows


def experience_entries(analysis: ResumeAnalysis) -> List[List[str]]:
    rows = []
    for entry in analysis.experience:
        lines = []
        if entry.title and entry.organization:
            lines.append(f"{entry.title} — {entry.organization}")
        elif entry.title or entry.organization:
            lines.append(entry.title or entry.organization)
        dates = " – ".join(part for part in (entry.start_date, entry.end_date) if part)
        if entry.is_current and dates and "present" not in dates.lower():
            dates = f"{dates} (current)"
        elif entry.is_current and not dates:
            dates = "current"
        if dates:
            lines.append(dates)
        lines.extend(line for line in entry.description if line.strip())
        if not lines and entry.raw_text.strip():
            lines.append(entry.raw_text.strip())
        rows.append(lines or ["An experience entry was returned without structured fields."])
    return rows


def project_entries(analysis: ResumeAnalysis) -> List[List[str]]:
    rows = []
    for entry in analysis.projects:
        lines = []
        if entry.name:
            lines.append(entry.name)
        if entry.technologies:
            lines.append("Technologies: " + ", ".join(entry.technologies))
        lines.extend(line for line in entry.description if line.strip())
        lines.extend(f"Link: {url}" for url in getattr(entry, "links", []) or [])
        if not lines and entry.raw_text.strip():
            lines.append(entry.raw_text.strip())
        rows.append(lines or ["A project entry was returned without structured fields."])
    return rows


def certification_lines(analysis: ResumeAnalysis) -> List[str]:
    lines = []
    for entry in analysis.certifications:
        bits = [bit for bit in (entry.kind, entry.name, entry.issuer, None if entry.year is None else str(entry.year)) if bit]
        if bits:
            lines.append(" — ".join(bits))
        elif entry.raw_text.strip():
            lines.append(entry.raw_text.strip())
    return lines


def extracted_preview(analysis: ResumeAnalysis) -> str:
    """Section text the pipeline kept. This is not a second read of the file."""
    parts = []
    for section in analysis.sections:
        if section.heading:
            parts.append(section.heading)
        body = section.content.strip()
        if body:
            parts.append(body)
    return "\n\n".join(parts)


def status_notice(analysis: ResumeAnalysis) -> Tuple[str, str]:
    """Return ``(level, message)`` with level in error, warning, or info."""
    if analysis.status == STATUS_FAILED:
        detail = " ".join(analysis.errors) or "The file could not be read."
        return "error", detail
    if analysis.status == STATUS_EMPTY:
        return (
            "warning",
            "The file was read, but it does not contain enough meaningful text to analyse.",
        )
    if analysis.status == STATUS_NEEDS_OCR:
        if analysis.source_format == "image":
            return (
                "warning",
                "This file is a photograph or image of a resume. OCR was not run, so no text was extracted. "
                "Turn on OCR and analyze again. That step needs a local Tesseract installation.",
            )
        return (
            "warning",
            "This PDF has too little selectable text, so nothing was extracted. "
            "It may be a scan. OCR was not run. Turn on “Use OCR for scanned PDFs” and analyze again. "
            "That step needs a local Tesseract installation.",
        )
    if analysis.status == STATUS_PARTIAL:
        return (
            "warning",
            "Extraction is incomplete. Some headings or details were not found. Blank fields were left blank.",
        )
    if analysis.status == STATUS_SUCCESS:
        return (
            "info",
            "Extraction finished. These are rule-based readings from the file, not verified facts.",
        )
    return "warning", f"The pipeline returned status '{analysis.status}'."


def has_structured_result(analysis: ResumeAnalysis) -> bool:
    return analysis.status in {STATUS_SUCCESS, STATUS_PARTIAL}


# Pipeline findings. These stay on ``analysis.warnings`` so a missed employment
# section can still be distinguished from a resume that has no such section.
_EXPERIENCE_NOT_DETECTED = "Section not detected: experience."
_EXPERIENCE_UNPARSED = "An Experience section was found but no job entries could be identified."
FRESHER_EXPERIENCE_MESSAGE = (
    "No professional experience section found. That's okay for freshers. "
    "Your projects and skills can still be evaluated."
)


def display_warnings(analysis: ResumeAnalysis) -> List[Tuple[str, str]]:
    """User-facing ``(level, message)`` notices.

    A missing Experience heading is an info notice. Every other pipeline
    warning, including a heading that was found but not parsed, stays a warning.
    """
    notices = []
    for warning in analysis.warnings:
        if warning == _EXPERIENCE_NOT_DETECTED:
            notices.append(("info", FRESHER_EXPERIENCE_MESSAGE))
        else:
            notices.append(("warning", warning))
    return notices


_GAP_LABELS = {
    "missing_required": "Missing required skill",
    "missing_preferred": "Missing preferred skill",
    "missing_unspecified": "Missing skill, priority not stated",
    "related": "Related evidence is not enough",
    "prerequisite": "Prerequisite",
    "unverified_experience": "Unverified professional experience",
    "short_experience": "Dated experience is shorter than the posting",
    "evidence_gap": "Evidence gap",
}


def _gap_label(kind: str) -> str:
    return _GAP_LABELS.get(kind, kind or "Gap")


def github_profile_lines(github) -> List[str]:
    """Profile facts. A missing count stays missing; zero stays zero."""
    if github is None:
        return []
    lines = []
    if getattr(github, "username", None):
        lines.append(f"Username: {github.username}")
    if getattr(github, "profile_url", None):
        lines.append(f"Profile: {github.profile_url}")
    if getattr(github, "name", None):
        lines.append(f"Name: {github.name}")
    if getattr(github, "bio", None):
        lines.append(f"Bio: {github.bio}")
    reported = getattr(github, "public_repos", None)
    if reported is None:
        lines.append("Public repositories reported by GitHub: not provided")
    else:
        lines.append(f"Public repositories reported by GitHub: {reported}")
    read_count = len(getattr(github, "repositories", []) or [])
    lines.append(f"Public non-fork repositories read: {read_count}")
    lines.append("Repository counts and push times are not a measure of professional ability.")
    return lines


def github_repository_lines(repository) -> List[str]:
    """One repository. Empty fields say they were absent, not zero."""
    lines = [repository.name, repository.url]
    if repository.description:
        lines.append(repository.description)
    else:
        lines.append("No description was provided.")
    warnings = " ".join(repository.warnings).lower()
    if repository.languages:
        lines.append("Languages: " + ", ".join(repository.languages))
    elif "language" in warnings:
        lines.append("Languages: not available")
    else:
        lines.append("Languages: none listed")
    if repository.pushed_at:
        lines.append(
            f"Last push recorded by GitHub: {repository.pushed_at}. This is not a measure of ability."
        )
    else:
        lines.append("Last push time: not provided")
    return lines


def github_skill_lines(github) -> List[str]:
    """Observed repository skills. These are not resume evidence."""
    skills = getattr(github, "skills", None) or []
    if not skills:
        return ["No taxonomy skills were observed in the repositories that were read."]
    lines = ["Observed in a public repository. This is not resume evidence and not a proficiency level."]
    seen = set()
    for skill in skills:
        key = (skill.skill_name, skill.repository, skill.source_field)
        if key in seen:
            continue
        seen.add(key)
        lines.append(f"{skill.skill_name} · {skill.repository} · {skill.source_field} · {skill.repository_url}")
    return lines


def readiness_lines(readiness) -> List[str]:
    """Show the assessment's own estimate. This function does not rescore it."""
    if readiness is None:
        return ["Readiness was not calculated."]
    lines = [readiness.disclaimer, readiness.summary]
    if readiness.estimate is None:
        if readiness.job_specific:
            lines.append(
                "No numeric estimate was calculated. "
                "The rubric scores only required items that are not unverified, and this comparison has none."
            )
        else:
            lines.append("No numeric estimate was calculated.")
    else:
        lines.append(f"Rule-based estimate: {readiness.estimate} out of 100 ({readiness.band}).")
        scored_count = sum(1 for item in readiness.criteria if item.scored)
        unverified_count = sum(
            1 for item in readiness.criteria
            if item.status == "unverified" and item.priority == "required"
        )
        preferred_count = sum(1 for item in readiness.criteria if item.priority == "preferred")
        unspecified_count = sum(1 for item in readiness.criteria if item.priority == "unspecified")
        lines.append(
            f"The denominator is {scored_count} scored required item(s). "
            f"{unverified_count} unverified required item(s), {preferred_count} preferred item(s), "
            f"and {unspecified_count} unspecified item(s) are shown and are not in the denominator. "
            f"A matched required item contributes {config.READINESS_MATCHED_CREDIT:g}. "
            f"A related or missing required item contributes {config.READINESS_UNSATISFIED_CREDIT:g}."
        )
    for item in readiness.criteria:
        scored = "scored" if item.scored else "not scored"
        lines.append(
            f"{item.name} · {item.priority} · {item.status} · {scored} · credit {item.credit:g}"
        )
        if item.posting_text:
            lines.append(f"Posting: {item.posting_text}")
        if item.detail:
            lines.append(item.detail)
    for note in readiness.github_observations:
        lines.append(f"GitHub observation: {note}")
    for note in readiness.limitations:
        if note != readiness.disclaimer:
            lines.append(note)
    return lines


def recommendation_lines(recommendations) -> List[str]:
    """Recommendation text in the engine's order."""
    if recommendations is None or recommendations.status != "success":
        reason = None if recommendations is None else recommendations.reason
        return [reason or "No recommendations were calculated."]
    if not recommendations.items and not recommendations.experience_gaps:
        return ["No skill or experience gaps were found for this posting."]
    lines = []
    for item in recommendations.items:
        lines.append(f"{item.skill_name} · {_gap_label(item.gap_kind)} · {item.priority}")
        lines.append(item.reason)
        if item.prerequisites:
            lines.append("Prerequisites: " + ", ".join(item.prerequisites))
        if item.practice_task:
            lines.append(item.practice_task)
    for item in recommendations.experience_gaps:
        lines.append(f"{item.skill_name} · {_gap_label(item.gap_kind)}")
        lines.append(item.reason)
        if item.practice_task:
            lines.append(item.practice_task)
    return lines


def roadmap_lines(roadmap) -> List[str]:
    """Ordered milestones. A weekly budget is a note, not a promised duration."""
    if roadmap is None or roadmap.status != "success" or not roadmap.milestones:
        reason = None if roadmap is None else roadmap.reason
        return [reason or "No roadmap was generated."]
    lines = [
        "Milestones follow prerequisite order. Required gaps come before preferred gaps, "
        "and a gap whose priority was not stated comes after those. "
        "No measured study duration is assigned, and a weekly budget is not a guarantee."
    ]
    if roadmap.planning_note:
        lines.append(roadmap.planning_note)
    for index, item in enumerate(roadmap.milestones, start=1):
        lines.append(f"{index}. {item.title} · {_gap_label(item.kind)}")
        lines.append(f"Objective: {item.objective}")
        if item.practice_task:
            lines.append(f"Task: {item.practice_task}")
        if item.demonstration:
            lines.append(f"Done when: {item.demonstration}")
    return lines


def experience_tab_notice(analysis: ResumeAnalysis) -> Optional[str]:
    """Caption for an empty Experience tab. Projects are not employment."""
    if analysis.experience:
        return None
    if _EXPERIENCE_NOT_DETECTED in analysis.warnings:
        return FRESHER_EXPERIENCE_MESSAGE
    if _EXPERIENCE_UNPARSED in analysis.warnings:
        return _EXPERIENCE_UNPARSED
    return None


_GROUP_HEADINGS = (
    (OUTCOME_MATCHED, "Matched"),
    (OUTCOME_RELATED, "Related, not a match"),
    (OUTCOME_MISSING, "Missing"),
    (OUTCOME_INDETERMINATE, "Not enough information"),
)


def _requirement_label(requirement: JobRequirement) -> str:
    if requirement.kind == "skill" and requirement.alternatives:
        return " or ".join(requirement.alternatives)
    if requirement.kind == "skill" and requirement.skill_name:
        return requirement.skill_name
    if requirement.kind == "degree":
        level = (requirement.degree_level or "degree").capitalize()
        if requirement.degree_field:
            return f"{level} in {requirement.degree_field}"
        return level
    if requirement.kind == "certification" and requirement.certification_name:
        return requirement.certification_name
    if requirement.kind == "experience":
        if requirement.years_min is not None and requirement.years_max is not None:
            label = f"{requirement.years_min:g}–{requirement.years_max:g} years of experience"
        elif requirement.years_min is not None:
            label = f"{requirement.years_min:g} years of experience"
        else:
            label = "Experience length was not stated as a number"
        if requirement.experience_focus:
            return f"{label} with {requirement.experience_focus}"
        return label
    return requirement.text


@dataclass
class ComparisonRow:
    """One requirement as the page should show it. No proficiency and no score."""

    outcome: str
    priority: str
    label: str
    requirement_text: str
    evidence_type: Optional[str]
    evidence_lines: List[str]
    related_skills: List[str]
    note: Optional[str]

    def display_lines(self) -> List[str]:
        head = f"{self.label} · {self.priority}"
        if self.outcome == OUTCOME_MATCHED and self.evidence_type:
            head += f" · {self.evidence_type}"
        elif self.outcome == OUTCOME_RELATED:
            head += " · related, not a match"
        lines = [head]
        lines.extend(f"Resume line: {line}" for line in self.evidence_lines)
        if self.related_skills:
            lines.append("Same category, not a match: " + ", ".join(self.related_skills))
        if self.note:
            lines.append(self.note)
        if self.requirement_text:
            lines.append(f"Posting: {self.requirement_text}")
        return lines


def _row_from_match(match) -> ComparisonRow:
    """Copy resume lines only for a match. Related skills stay in their own field."""
    evidence_type = None
    evidence_lines: List[str] = []
    if match.outcome == OUTCOME_MATCHED:
        if match.evidence_type in ("used", "mentioned"):
            evidence_type = match.evidence_type
        if match.evidence:
            evidence_lines = [item.text for item in match.evidence if item.text]
        elif match.support:
            evidence_lines = [line for line in match.support if line]
    label = _requirement_label(match.requirement)
    if match.outcome == OUTCOME_INDETERMINATE and match.requirement.kind == "experience":
        label = f"{label} · unverified"
    return ComparisonRow(
        outcome=match.outcome,
        priority=match.requirement.priority,
        label=label,
        requirement_text=match.requirement.text,
        evidence_type=evidence_type,
        evidence_lines=evidence_lines,
        related_skills=list(match.related_skills) if match.outcome == OUTCOME_RELATED else [],
        note=match.note,
    )


def comparison_groups(report: MatchReport) -> List[Tuple[str, str, List[ComparisonRow]]]:
    """``(outcome, heading, rows)`` for matched, related, missing, then indeterminate."""
    buckets = {outcome: [] for outcome, _heading in _GROUP_HEADINGS}
    for match in report.matches:
        buckets.setdefault(match.outcome, []).append(_row_from_match(match))
    return [(outcome, heading, buckets.get(outcome, [])) for outcome, heading in _GROUP_HEADINGS]


def job_feedback(job: JobAnalysis, report: MatchReport) -> Tuple[str, str]:
    """``(level, message)`` for a job comparison. Level is error, warning, or info."""
    if report.status in {STATUS_FAILED, STATUS_EMPTY, STATUS_NEEDS_OCR} and job.status == STATUS_SUCCESS:
        message = report.reason or "The resume could not be read, so requirements were not compared."
        return ("error" if report.status == STATUS_FAILED else "warning"), message
    if job.status == STATUS_FAILED or report.status == STATUS_FAILED:
        message = job.reason or " ".join(job.errors) or report.reason or "The job description could not be read."
        return "error", message
    if job.status == STATUS_EMPTY or report.status == STATUS_EMPTY:
        return "warning", job.reason or report.reason or "No meaningful text was found, so no requirements could be extracted."
    if job.status == STATUS_NEEDS_OCR or report.status == STATUS_NEEDS_OCR:
        message = job.reason or report.reason or "The file does not contain enough extractable text."
        if "OCR" not in message:
            message = message.rstrip(".") + ". OCR was not run for job descriptions."
        return "warning", message
    if job.status == STATUS_PARTIAL or report.status == STATUS_PARTIAL:
        return "warning", report.reason or job.reason or "No requirements could be identified."
    if report.matches:
        return (
            "info",
            "Requirements are grouped by outcome. Related skills are not matches. Proficiency is not inferred.",
        )
    return "warning", report.reason or job.reason or "Nothing was compared."
