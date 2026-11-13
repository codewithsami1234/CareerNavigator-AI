"""Downloads built only from objects the pipeline already returned."""
from __future__ import annotations

import csv
import io
import json
from typing import Any, Optional


def _dump(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return None


def report_payload(analysis, job, comparison, github, career) -> dict:
    return {
        "resume": _dump(analysis),
        "job": _dump(job),
        "comparison": _dump(comparison),
        "github": _dump(github),
        "career_report": _dump(career),
        "limitations": [
            "Readings come from the local rule-based pipeline.",
            "A readiness figure is not a hiring prediction and not an ATS score.",
            "GitHub rows are public metadata. Source code was not analyzed.",
            "The job text was supplied for this session. Listings were not scraped.",
        ],
    }


def report_json(analysis, job, comparison, github, career) -> str:
    return json.dumps(
        report_payload(analysis, job, comparison, github, career),
        indent=2,
        ensure_ascii=False,
    )


def skills_csv(analysis) -> Optional[str]:
    skills = getattr(analysis, "skills", None) or []
    if not skills:
        return None
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["skill", "category", "evidence_type", "mention_count", "evidence"])
    for skill in skills:
        evidence = " | ".join(
            item.text for item in getattr(skill, "evidence", []) or [] if getattr(item, "text", None)
        )
        writer.writerow([
            skill.name,
            skill.category,
            skill.evidence_type,
            skill.mention_count,
            evidence,
        ])
    return buffer.getvalue()


def comparison_csv(report) -> Optional[str]:
    matches = getattr(report, "matches", None) or []
    if not matches:
        return None
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["outcome", "priority", "kind", "label", "text", "evidence_type", "note"])
    for match in matches:
        requirement = match.requirement
        label = requirement.skill_name or requirement.certification_name or requirement.kind
        writer.writerow([
            match.outcome,
            requirement.priority,
            requirement.kind,
            label,
            requirement.text,
            match.evidence_type or "",
            match.note or "",
        ])
    return buffer.getvalue()


def _add(lines: list, text: str = "") -> None:
    lines.append(text)


def _contact_lines(analysis) -> list:
    contact = getattr(analysis, "contact", None)
    labels = (
        ("name", "Name"),
        ("email", "Email"),
        ("phone", "Phone"),
        ("location", "Location"),
        ("linkedin", "LinkedIn"),
        ("github", "GitHub"),
        ("leetcode", "LeetCode"),
        ("twitter", "X / Twitter"),
    )
    lines = ["## Extracted contact"]
    missing = []
    for key, label in labels:
        value = getattr(contact, key, None) if contact is not None else None
        if value:
            lines.append(f"- {label}: {value}")
        else:
            missing.append(label)
    if len(lines) == 1:
        lines.append("- No contact fields were extracted.")
    lines.append("")
    lines.append("Not found in the extracted text: " + ", ".join(missing) + ".")
    lines.append("Missing fields are omitted. They are not filled in.")
    return lines


def _skill_lines(analysis) -> list:
    skills = list(getattr(analysis, "skills", None) or [])
    lines = ["## Extracted skills"]
    if not skills:
        lines.append("No taxonomy skills were extracted.")
        return lines
    groups: dict = {}
    for skill in skills:
        groups.setdefault(getattr(skill, "category", None) or "Uncategorised", []).append(skill)
    for category in sorted(groups):
        lines.append(f"### {category}")
        for skill in groups[category]:
            lines.append(
                f"- {skill.name} — evidence type `{skill.evidence_type}`, "
                f"{skill.mention_count} distinct line(s)"
            )
            for item in getattr(skill, "evidence", None) or []:
                lines.append(f"  - [{item.section}] {item.text}")
    return lines


def _entry_lines(title: str, entries, formatter) -> list:
    lines = [f"## {title}"]
    items = list(entries or [])
    if not items:
        lines.append(f"No {title.lower()} were extracted.")
        return lines
    for entry in items:
        lines.extend(formatter(entry))
    return lines


def readable_report(
    analysis,
    job,
    comparison,
    github,
    career,
    *,
    job_title: str = "",
    company: str = "",
    target_career: str = "",
) -> str:
    """Plain-text report built only from pipeline objects and labels the user typed.

    This function does not score anything. When a readiness estimate exists, it
    is copied from ``career.readiness``.
    """
    lines: list = [
        "# CareerNavigator AI report",
        "",
        "This document is assembled from the rule-based pipeline results.",
        "It does not add findings, job listings, or courses.",
        "This report does not calculate a second score.",
        "The readiness figure, when present, is copied from the pipeline estimate.",
        "That estimate is not a hiring prediction and it is not an ATS score.",
        "",
    ]
    labels = [("Target career", target_career), ("Job title", job_title), ("Company", company)]
    typed = [(label, value.strip()) for label, value in labels if value and value.strip()]
    if typed:
        _add(lines, "## Labels you entered")
        _add(lines, "These were typed into the form. They were not extracted from the resume or the job description.")
        for label, value in typed:
            lines.append(f"- {label}: {value}")
        _add(lines)

    if analysis is None:
        lines.extend(["## Resume", "No resume analysis was supplied.", ""])
    else:
        lines.extend([
            "## Resume",
            f"- Status: {getattr(analysis, 'status', None)}",
            f"- File: {getattr(analysis, 'file_name', None) or '(none)'}",
            f"- Source format: {getattr(analysis, 'source_format', None)}",
            f"- Pages: {getattr(analysis, 'page_count', None)}",
            f"- Text length: {getattr(analysis, 'text_length', None)}",
            "",
        ])
        provenance = list(getattr(analysis, "text_provenance", None) or [])
        lines.append("## Text provenance")
        if not provenance:
            lines.append("No provenance records were returned. Phase 1 JSON omits this field when OCR was not used.")
        else:
            for item in provenance:
                lines.append(
                    f"- Page {item.page_number}: {item.method}, {item.char_count} characters"
                    + (f", OCR confidence {item.confidence}" if item.confidence is not None else "")
                    + (" (duplicate suppressed)" if item.suppressed_duplicate else "")
                )
        lines.append("")
        quality = getattr(analysis, "quality_report", None)
        lines.append("## Document quality")
        findings = list(getattr(quality, "findings", None) or [])
        if not findings:
            lines.append("No quality findings were returned.")
        for finding in findings:
            lines.append(f"- [{finding.severity}/{finding.kind}] {finding.message}")
        for note in list(getattr(quality, "limitations", None) or []):
            lines.append(f"- Limitation: {note}")
        lines.append("")
        lines.extend(_contact_lines(analysis))
        lines.append("")
        lines.extend(_skill_lines(analysis))
        lines.append("")

        def education(entry):
            return [f"- {entry.raw_text or entry.degree or entry.institution or 'Education entry'}"]

        def experience(entry):
            title = " | ".join(part for part in (entry.title, entry.organization) if part) or "Experience entry"
            block = [f"- {title}"]
            if entry.start_date or entry.end_date:
                block.append(f"  - Dates: {entry.start_date or '?'} – {entry.end_date or '?'}")
            for bullet in entry.description or []:
                block.append(f"  - {bullet}")
            return block

        def project(entry):
            block = [f"- {entry.name or 'Project'}"]
            if entry.technologies:
                block.append(f"  - Taxonomy skills named in the entry: {', '.join(entry.technologies)}")
            for bullet in entry.description or []:
                block.append(f"  - {bullet}")
            return block

        def certification(entry):
            return [f"- {entry.raw_text or entry.name or entry.kind}"]

        lines.extend(_entry_lines("Education", getattr(analysis, "education", None), education))
        lines.append("")
        lines.extend(_entry_lines("Experience", getattr(analysis, "experience", None), experience))
        lines.append("")
        lines.extend(_entry_lines("Projects", getattr(analysis, "projects", None), project))
        lines.append("")
        lines.extend(_entry_lines("Certifications and courses", getattr(analysis, "certifications", None), certification))
        lines.append("")
        lines.append("## Extracted sections")
        sections = list(getattr(analysis, "sections", None) or [])
        if not sections:
            lines.append("No sections were detected.")
        for section in sections:
            heading = section.heading or section.name
            lines.append(f"### {heading} ({section.name})")
            lines.append(section.content or "(empty)")
            lines.append("")
        warnings = list(getattr(analysis, "warnings", None) or [])
        errors = list(getattr(analysis, "errors", None) or [])
        lines.append("## Resume warnings and errors")
        if not warnings and not errors:
            lines.append("None returned.")
        for warning in warnings:
            lines.append(f"- Warning: {warning}")
        for error in errors:
            lines.append(f"- Error: {error}")
        lines.append("")

    lines.append("## Job description")
    if job is None:
        lines.append("No job description was supplied. Listings are not fetched by this application.")
    else:
        lines.append(f"- Status: {getattr(job, 'status', None)}")
        if getattr(job, "reason", None):
            lines.append(f"- Reason: {job.reason}")
        requirements = list(getattr(job, "requirements", None) or [])
        lines.append(f"- Requirements extracted: {len(requirements)}")
        for item in requirements:
            label = item.skill_name or item.certification_name or item.degree_level or item.kind
            lines.append(f"- [{item.priority}] {item.kind}: {label} — {item.text}")
        for warning in getattr(job, "warnings", None) or []:
            lines.append(f"- Warning: {warning}")
        for error in getattr(job, "errors", None) or []:
            lines.append(f"- Error: {error}")
    lines.append("")

    lines.append("## Comparison")
    lines.append("Outcomes are matched, related, missing, or indeterminate. Related is not a match.")
    if comparison is None:
        lines.append("No comparison was produced.")
    else:
        lines.append(
            f"- Matched {comparison.matched_count}, related {comparison.related_count}, "
            f"missing {comparison.missing_count}, indeterminate {comparison.indeterminate_count}."
        )
        for match in comparison.matches or []:
            requirement = match.requirement
            label = requirement.skill_name or requirement.certification_name or requirement.kind
            lines.append(f"- {match.outcome} [{requirement.priority}] {label}: {requirement.text}")
            if match.note:
                lines.append(f"  - Note: {match.note}")
            for item in match.evidence or []:
                lines.append(f"  - Resume evidence [{item.section}, {item.evidence_type}]: {item.text}")
            for support in match.support or []:
                lines.append(f"  - Support: {support}")
            if match.related_skills:
                lines.append(f"  - Related, not matched: {', '.join(match.related_skills)}")
        for warning in comparison.warnings or []:
            lines.append(f"- Warning: {warning}")
    lines.append("")

    readiness = getattr(career, "readiness", None) if career is not None else None
    lines.append("## Readiness estimate")
    if readiness is None:
        lines.append("No readiness object was returned.")
    else:
        lines.append(readiness.disclaimer)
        shown = readiness.estimate if readiness.estimate is not None else "Not scored"
        lines.append(f"- Estimate: {shown}")
        lines.append(f"- Band: {readiness.band}")
        lines.append(f"- Summary: {readiness.summary}")
        for item in readiness.criteria or []:
            scored = "in the denominator" if item.scored else "not scored"
            lines.append(
                f"- {item.name}: {item.status}, priority {item.priority}, credit {item.credit:g}, {scored}"
            )
            if item.detail:
                lines.append(f"  - {item.detail}")
            for evidence in item.resume_evidence or []:
                lines.append(f"  - Evidence: {evidence}")
        for note in readiness.github_observations or []:
            lines.append(f"- GitHub observation: {note}")
        for note in readiness.limitations or []:
            if note != readiness.disclaimer:
                lines.append(f"- Limitation: {note}")
    lines.append("")

    recommendations = getattr(career, "recommendations", None) if career is not None else None
    lines.append("## Skill gaps and suggestions")
    lines.append("Suggestions are traceable to comparison outcomes. They are not a hiring judgment.")
    lines.append("Prerequisite links come from a local sequencing map. The posting may not have named them.")
    if recommendations is None or getattr(recommendations, "status", None) == "unavailable":
        reason = getattr(recommendations, "reason", None) if recommendations is not None else None
        lines.append(reason or "No role-specific gaps were calculated.")
    else:
        if recommendations.matched_skills:
            lines.append("Matched skills: " + ", ".join(recommendations.matched_skills) + ".")
        for item in list(recommendations.items or []) + list(recommendations.experience_gaps or []):
            lines.append(f"- {item.skill_name} ({item.gap_kind}, {item.priority})")
            lines.append(f"  - Why: {item.reason}")
            if item.posting_text:
                lines.append(f"  - Posting text: {item.posting_text}")
            if item.practice_task:
                lines.append(f"  - Practice: {item.practice_task}")
            if item.prerequisites:
                lines.append(f"  - Local prerequisites: {', '.join(item.prerequisites)}")
        for note in recommendations.limitations or []:
            lines.append(f"- Limitation: {note}")
    lines.append("")

    roadmap = getattr(career, "roadmap", None) if career is not None else None
    lines.append("## Roadmap")
    lines.append("Milestones are suggestions sequenced from the gaps above. No course catalogue is attached.")
    if roadmap is None or getattr(roadmap, "status", None) == "unavailable":
        reason = getattr(roadmap, "reason", None) if roadmap is not None else None
        lines.append(reason or "No roadmap was produced.")
    else:
        if roadmap.planning_note:
            lines.append(roadmap.planning_note)
        for index, item in enumerate(roadmap.milestones or [], start=1):
            lines.append(f"{index}. {item.title} (source: {item.source})")
            lines.append(f"   - Objective: {item.objective}")
            lines.append(f"   - Practice: {item.practice_task}")
            lines.append(f"   - What to keep as evidence: {item.demonstration}")
            if item.posting_text:
                lines.append(f"   - Posting text: {item.posting_text}")
            if item.prerequisites:
                lines.append(f"   - Prerequisites: {', '.join(item.prerequisites)}")
        for note in roadmap.limitations or []:
            lines.append(f"- Limitation: {note}")
    lines.append("")

    guidance = getattr(career, "guidance", None) if career is not None else None
    lines.append("## Evidence-based guidance")
    lines.append("These notes restate extracted evidence and comparison outcomes. They do not change the readiness estimate.")
    if guidance is None or getattr(guidance, "status", None) == "unavailable":
        reason = getattr(guidance, "reason", None) if guidance is not None else None
        lines.append(reason or "No guidance was produced.")
    else:
        def _guide(title: str, rows) -> None:
            lines.append(title)
            if not rows:
                lines.append("- None.")
                return
            for item in rows:
                lines.append(f"- {item.title}: {item.reason}")

        _guide("Skills to strengthen:", guidance.skills_to_strengthen)
        _guide("Partially supported:", guidance.partially_supported)
        _guide("Project ideas:", guidance.project_ideas)
        _guide("Career-path labels:", guidance.career_paths)
        _guide("Near-term roadmap:", guidance.short_term)
        _guide("Later roadmap:", guidance.long_term)
        _guide("Focus slots:", guidance.weekly_focus)
        if guidance.github_notes:
            lines.append("GitHub, separate from the resume:")
            for note in guidance.github_notes:
                lines.append(f"- {note}")
        for note in guidance.limitations or []:
            lines.append(f"- Limitation: {note}")
    lines.append("")

    lines.append("## GitHub")
    lines.append("Public metadata only. A language or topic in a repository is not proof of proficiency.")
    lines.append("At most eight recently pushed public non-fork repositories are read. Source code is not downloaded.")
    if github is None:
        lines.append("GitHub analysis was not requested.")
    else:
        lines.append(f"- Status: {github.status}")
        lines.append(f"- Username: {github.username or '(none)'}")
        if github.reason:
            lines.append(f"- Reason: {github.reason}")
        for error in github.errors or []:
            lines.append(f"- Error: {error}")
        if github.name:
            lines.append(f"- Name: {github.name}")
        if github.bio:
            lines.append(f"- Bio: {github.bio}")
        if github.public_repos is not None:
            lines.append(f"- Public repositories reported by the profile: {github.public_repos}")
        seen = []
        for skill in github.skills or []:
            if skill.skill_name not in seen:
                seen.append(skill.skill_name)
        if seen:
            lines.append("- Taxonomy skills observed in public metadata: " + ", ".join(seen) + ".")
        else:
            lines.append("- No taxonomy skills were observed in the scanned public metadata.")
        for repo in github.repositories or []:
            languages = ", ".join(repo.languages) if repo.languages else "none listed"
            pushed = f", last push {repo.pushed_at}" if getattr(repo, "pushed_at", None) else ""
            lines.append(f"- {repo.name} ({repo.url}) — languages: {languages}{pushed}")
            if repo.description:
                lines.append(f"  - {repo.description}")
        for note in github.limitations or []:
            lines.append(f"- Limitation: {note}")
        for warning in github.warnings or []:
            lines.append(f"- Warning: {warning}")
    lines.append("")
    lines.append("## Report limitations")
    for note in (
        "Readings come from the local rule-based pipeline.",
        "A readiness figure is not a hiring prediction and not an ATS score.",
        "GitHub rows are public metadata. Source code was not analyzed.",
        "The job text was supplied for this session. Listings were not scraped.",
        "Checked roadmap items, if any, were marked in the browser and are not verified learning.",
    ):
        lines.append(f"- {note}")
    if career is not None:
        for note in getattr(career, "limitations", None) or []:
            lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _pdf_blocks(markdown: str) -> list:
    blocks = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if not line.strip():
            blocks.append(("gap", ""))
            continue
        if line.startswith("### "):
            blocks.append(("h3", line[4:].strip()))
        elif line.startswith("## "):
            blocks.append(("h2", line[3:].strip()))
        elif line.startswith("# "):
            blocks.append(("h1", line[2:].strip()))
        else:
            blocks.append(("body", line))
    return blocks


def _wrap_long_tokens(text: str, limit: int = 48) -> str:
    pieces = []
    for token in text.split(" "):
        if len(token) <= limit:
            pieces.append(token)
            continue
        pieces.append(" ".join(token[index:index + limit] for index in range(0, len(token), limit)))
    return " ".join(pieces)


def _text_width(text: str, fontname: str, fontsize: float) -> float:
    import pymupdf
    return float(pymupdf.get_text_length(text, fontname=fontname, fontsize=fontsize))


def _wrap_line(text: str, fontname: str, fontsize: float, width: float) -> list:
    words = _wrap_long_tokens(text).split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if _text_width(trial, fontname, fontsize) <= width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def report_pdf(
    analysis,
    job,
    comparison,
    github,
    career,
    *,
    job_title: str = "",
    company: str = "",
    target_career: str = "",
) -> bytes:
    """Real PDF of the same report text. It does not score or add findings."""
    import pymupdf

    markdown = readable_report(
        analysis, job, comparison, github, career,
        job_title=job_title, company=company, target_career=target_career,
    )
    styles = {
        "h1": ("hebo", 16, 18, 8),
        "h2": ("hebo", 13, 16, 6),
        "h3": ("hebo", 11, 14, 4),
        "body": ("helv", 10, 14, 1),
    }
    espresso = (0.161, 0.145, 0.122)
    gold = (0.839, 0.718, 0.478)
    cream = (0.973, 0.953, 0.914)
    page_width, page_height = 595.0, 842.0
    margin = 54.0
    content_width = page_width - margin * 2
    header_bottom = 50.0
    footer_limit = page_height - 40.0
    document = pymupdf.open()

    def new_page():
        page = document.new_page(width=page_width, height=page_height)
        page.draw_rect(pymupdf.Rect(0, 0, page_width, 32), color=None, fill=cream)
        page.draw_rect(pymupdf.Rect(0, 32, page_width, 36), color=None, fill=gold)
        page.insert_text((margin, 22), "CareerNavigator AI", fontsize=12, fontname="hebo", color=espresso)
        return page, header_bottom

    page, cursor = new_page()

    def ensure(height: float) -> None:
        nonlocal page, cursor
        if cursor + height > footer_limit:
            page, cursor = new_page()

    for kind, text in _pdf_blocks(markdown):
        if kind == "gap":
            cursor += 8
            continue
        fontname, fontsize, line_height, before = styles[kind]
        ensure(before + line_height)
        cursor += before
        for line in _wrap_line(text, fontname, fontsize, content_width):
            ensure(line_height)
            page.insert_text((margin, cursor + fontsize), line, fontsize=fontsize, fontname=fontname, color=espresso)
            cursor += line_height

    total = document.page_count
    for index, pdf_page in enumerate(document, start=1):
        pdf_page.insert_text(
            (page_width - margin - 78, page_height - 22),
            f"Page {index} of {total}",
            fontsize=9,
            fontname="helv",
            color=espresso,
        )
    payload = document.tobytes()
    document.close()
    return payload
