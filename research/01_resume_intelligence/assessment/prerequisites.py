"""Documented prerequisite links used by recommendations and the roadmap.

These are editorial relationships for sequencing practice, not measured
learning times and not job requirements. A name is included only when the
later skill is normally practiced after the earlier one.
"""
from __future__ import annotations

from typing import Dict, List

# Later skill -> skills that should be practiced first when they are not already evidenced.
# Functional programming is a foundation for the JavaScript and React gaps below.
# It is not inserted unless that gap itself is missing.
PREREQUISITES: Dict[str, List[str]] = {
    "functional programming": ["JavaScript"],
    "TypeScript": ["JavaScript"],
    "React": ["JavaScript"],
    "Webflow": ["HTML", "CSS", "JavaScript"],
    "React hooks": ["JavaScript", "React"],
    "Redux": ["JavaScript", "React"],
    "Flux": ["JavaScript", "React"],
    "state management": ["JavaScript", "React"],
    "Next.js": ["JavaScript", "React"],
    "React Native": ["JavaScript", "React"],
    "Express.js": ["JavaScript", "Node.js"],
    "Django": ["Python"],
    "Flask": ["Python"],
    "FastAPI": ["Python"],
    "Pandas": ["Python"],
    "NumPy": ["Python"],
    "PyTorch": ["Python"],
    "TensorFlow": ["Python"],
    "scikit-learn": ["Python"],
    "Spring Boot": ["Java"],
    "Kubernetes": ["Docker"],
}

# Lower numbers come first when the gaps exist. Unknown names stay later.
SEQUENCE_RANK: Dict[str, int] = {
    "JavaScript": 10,
    "HTML": 12,
    "CSS": 14,
    "functional programming": 20,
    "TypeScript": 30,
    "React": 40,
    "Webflow": 45,
    "React hooks": 50,
    "Redux": 60,
    "Flux": 60,
    "state management": 60,
    "REST API": 70,
    "testing": 80,
    "Unit Testing": 81,
    "Jest": 82,
    "Pytest": 83,
    "JUnit": 83,
    "build automation": 85,
    "CI/CD": 90,
    "Jenkins": 91,
    "GitHub Actions": 91,
    "GitLab CI": 92,
    "Docker": 100,
    "Linux": 110,
    "Bash": 120,
    "Kubernetes": 130,
}


def prerequisites_for(skill_name: str) -> List[str]:
    return list(PREREQUISITES.get(skill_name, []))


def sequence_rank(skill_name: str) -> int:
    """Curriculum position. An ``A or B`` label uses the earlier of the two."""
    parts = [part.strip() for part in (skill_name or "").split(" or ")] or [skill_name or ""]
    ranks = [SEQUENCE_RANK[part] for part in parts if part in SEQUENCE_RANK]
    if ranks:
        return min(ranks)
    return 400
