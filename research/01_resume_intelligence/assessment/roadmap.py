"""Sequence the same skill-gap recommendations into milestones.

No course URL, completion date, or measured study duration is invented. A
weekly time budget only adds a planning note.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set

from assessment.prerequisites import sequence_rank
from assessment.recommendations import Recommendation, RecommendationReport
from schemas import STATUS_SUCCESS


@dataclass
class Milestone:
    title: str
    objective: str
    practice_task: str
    demonstration: str
    kind: str
    skill_name: Optional[str] = None
    posting_text: Optional[str] = None
    prerequisites: List[str] = field(default_factory=list)
    source: str = "suggestion"


@dataclass
class Roadmap:
    status: str = "unavailable"
    reason: Optional[str] = None
    milestones: List[Milestone] = field(default_factory=list)
    planning_note: Optional[str] = None
    limitations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def _synthetic(name: str, dependent: Recommendation) -> Recommendation:
    return Recommendation(
        skill_name=name,
        priority="prerequisite",
        gap_kind="prerequisite",
        reason=(
            f"{name} is listed as a prerequisite of {dependent.skill_name} in the local sequencing map. "
            "The posting did not separately require it."
        ),
        posting_text=dependent.posting_text,
        prerequisites=[],
        practice_task=(
            f"Practice {name} before {dependent.skill_name}. "
            f"Do not add {name} to a resume until the practice exists."
        ),
    )


def _order_skills(
    items: List[Recommendation], matched: Set[str], shown: Set[str],
) -> List[Recommendation]:
    """Prerequisite order, then the local sequence among skills that are still gaps.

    A skill the resume already shows is not added as a prerequisite and is not
    treated as proof of proficiency. A required gap stays ahead of a preferred gap.
    """
    known = set(matched) | set(shown)
    nodes: Dict[str, Recommendation] = {}
    for item in items:
        if item.skill_name and item.skill_name not in matched:
            nodes[item.skill_name] = item
    growing = True
    while growing:
        growing = False
        for item in list(nodes.values()):
            for prereq in item.prerequisites:
                if not prereq or prereq in known or prereq in nodes:
                    continue
                nodes[prereq] = _synthetic(prereq, item)
                growing = True

    dependents: Dict[str, List[str]] = {}
    for item in nodes.values():
        for prereq in item.prerequisites:
            if prereq in nodes:
                dependents.setdefault(prereq, []).append(item.skill_name)

    band_of = {"missing_required": 0, "missing_preferred": 1, "missing_unspecified": 2, "related": 3}
    band_memo: Dict[str, int] = {}

    def band(name: str, stack: Optional[Set[str]] = None) -> int:
        if name in band_memo:
            return band_memo[name]
        item = nodes[name]
        if item.gap_kind != "prerequisite":
            value = band_of.get(item.gap_kind, 1)
            band_memo[name] = value
            return value
        stack = set(stack or ())
        if name in stack:
            band_memo[name] = 0
            return 0
        stack.add(name)
        users = dependents.get(name, [])
        value = min((band(user, stack) for user in users), default=0)
        band_memo[name] = value
        return value

    indegree = {name: 0 for name in nodes}
    edges: Dict[str, List[str]] = {name: [] for name in nodes}
    for item in nodes.values():
        for prereq in item.prerequisites:
            if prereq in nodes and prereq != item.skill_name:
                edges[prereq].append(item.skill_name)
                indegree[item.skill_name] += 1
    ready = [name for name, degree in indegree.items() if degree == 0]
    ordered_names: List[str] = []
    while ready:
        ready.sort(key=lambda name: (band(name), sequence_rank(name), name.lower()))
        current = ready.pop(0)
        ordered_names.append(current)
        for nxt in edges[current]:
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                ready.append(nxt)
    for name in nodes:
        if name not in ordered_names:
            ordered_names.append(name)
    return [nodes[name] for name in ordered_names]


def build_roadmap(
    recommendations: Optional[RecommendationReport],
    *,
    weekly_hours: Optional[int] = None,
) -> Roadmap:
    """Turn gap recommendations into ordered milestones."""
    limitations = [
        "Milestones are suggested activities, not verified completion.",
        "No external course is linked.",
        "No learning duration is estimated.",
        "A skill named on a resume is not treated as proof of proficiency.",
    ]
    if recommendations is None or recommendations.status != STATUS_SUCCESS:
        reason = None if recommendations is None else recommendations.reason
        reason = reason or "No skill-gap recommendations were available, so no roadmap was generated."
        return Roadmap(status="unavailable", reason=reason, limitations=limitations)

    matched = set(recommendations.matched_skills)
    shown = set(getattr(recommendations, "shown_skills", []) or [])
    skill_rows = _order_skills(recommendations.items, matched, shown)
    milestones: List[Milestone] = []
    for item in skill_rows:
        milestones.append(Milestone(
            title=item.skill_name,
            objective=f"Be able to use {item.skill_name} in a small, reviewable piece of work.",
            practice_task=item.practice_task,
            demonstration=f"A project or write-up that shows {item.skill_name} in use.",
            kind=item.gap_kind,
            skill_name=item.skill_name,
            posting_text=item.posting_text,
            prerequisites=list(item.prerequisites),
            source="suggestion",
        ))
    for item in recommendations.experience_gaps:
        milestones.append(Milestone(
            title=f"Employment evidence: {item.skill_name}",
            objective="Record dated employment that can be compared with the posting.",
            practice_task=item.practice_task,
            demonstration="A resume employment entry with an explicit start and end, or Present.",
            kind=item.gap_kind,
            skill_name=item.skill_name,
            posting_text=item.posting_text,
            source="evidence_gap",
        ))
    planning = None
    if weekly_hours is not None:
        if not isinstance(weekly_hours, int) or weekly_hours <= 0:
            planning = "The time budget was not a positive number of hours, so no schedule was applied."
        else:
            planning = (
                f"A budget of {weekly_hours} hours each week was supplied. "
                "Milestones stay in prerequisite order. No measured duration is assigned to a milestone."
            )
    return Roadmap(
        status=STATUS_SUCCESS if milestones else "unavailable",
        reason=None if milestones else "The comparison did not produce skill or experience gaps.",
        milestones=milestones,
        planning_note=planning,
        limitations=limitations,
    )
