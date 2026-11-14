"""Requirement rows copied from the job analysis. No extra requirements are added."""
from __future__ import annotations

from typing import List

from schemas import JobAnalysis


def requirement_lines(job: JobAnalysis) -> List[str]:
    lines = []
    for requirement in job.requirements:
        label = requirement.skill_name or requirement.certification_name or requirement.kind
        if requirement.kind == "degree" and requirement.degree_level:
            label = requirement.degree_level
            if requirement.degree_field:
                label = f"{label} in {requirement.degree_field}"
        if requirement.kind == "experience" and requirement.years_min is not None:
            label = f"{requirement.years_min:g} years"
            if requirement.experience_focus:
                label = f"{label} with {requirement.experience_focus}"
        lines.append(f"{requirement.kind} · {requirement.priority} · {label}")
        if requirement.text:
            lines.append(f"Posting: {requirement.text}")
    return lines
