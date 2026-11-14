"""Data models (plain dataclasses) shared by every module.

All models serialise to JSON through ``ResumeAnalysis.to_dict()`` / ``to_json()``.
Unknown values are represented as ``None`` or empty lists, never invented.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

import config

# ---- Document status values ------------------------------------------------
STATUS_SUCCESS = "success"      # text recovered, sections found, something was extracted
STATUS_PARTIAL = "partial"      # text recovered, but little/no structure could be detected
STATUS_NEEDS_OCR = "needs_ocr"  # PDF has no/too little extractable text (Phase 2: OCR)
STATUS_EMPTY = "empty"          # readable file, but no meaningful text inside
STATUS_FAILED = "failed"        # file could not be validated/opened/read

# Parser-level status values (internal to parsers).
PARSE_OK = "ok"

# Job-description priorities. ``unspecified`` means the posting did not say,
# or the heading and the line disagreed. It is not a guess.
PRIORITY_REQUIRED = "required"
PRIORITY_PREFERRED = "preferred"
PRIORITY_UNSPECIFIED = "unspecified"

# Comparison outcomes. ``related`` is the same skill category only and is never
# counted as a match. ``indeterminate`` means the text does not support a decision.
OUTCOME_MATCHED = "matched"
OUTCOME_RELATED = "related"
OUTCOME_MISSING = "missing"
OUTCOME_INDETERMINATE = "indeterminate"

REQUIREMENT_SKILL = "skill"
REQUIREMENT_DEGREE = "degree"
REQUIREMENT_CERTIFICATION = "certification"
REQUIREMENT_EXPERIENCE = "experience"

EXPERIENCE_STATED = "stated"
EXPERIENCE_INDETERMINATE = "indeterminate"


@dataclass
class DocumentLink:
    """A hyperlink target stored in the file (PDF link annotation or DOCX hyperlink).

    ``text`` is the visible anchor text, which may be only a label such as
    ``GitHub``. ``uri`` is the target exactly as stored in the file.
    """
    text: str
    uri: str
    page_number: Optional[int] = None


@dataclass
class ParseResult:
    """Output of a document parser (before any information extraction)."""
    text: str = ""
    source_format: str = "unknown"          # "pdf" | "docx" | "text" | "unknown"
    status: str = PARSE_OK                  # "ok" | STATUS_EMPTY | STATUS_NEEDS_OCR | STATUS_FAILED
    page_count: Optional[int] = None
    file_name: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    links: List[DocumentLink] = field(default_factory=list)


@dataclass
class ContactInfo:
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None          # only when explicitly stated
    linkedin: Optional[str] = None
    github: Optional[str] = None            # a profile URL, never a single repository
    leetcode: Optional[str] = None
    twitter: Optional[str] = None           # X / Twitter profile


@dataclass
class Section:
    name: str                               # canonical key, e.g. "experience" or "header"
    heading: Optional[str]                  # heading text exactly as written (None for header)
    start_line: int                         # 0-based line index in the cleaned text
    end_line: int                           # inclusive
    content: str = ""                       # text under the heading (heading line excluded)


@dataclass
class SkillEvidence:
    section: str
    text: str                               # the line in which the skill was found
    evidence_type: str                      # "used" | "mentioned"
    matched_as: str                         # the surface form that matched (e.g. "sklearn")


@dataclass
class DetectedSkill:
    name: str                               # canonical name from the taxonomy
    category: str
    evidence_type: str                      # "used" if any evidence is "used", else "mentioned"
    mention_count: int                      # number of distinct lines mentioning the skill
    matched_as: List[str] = field(default_factory=list)
    evidence: List[SkillEvidence] = field(default_factory=list)


@dataclass
class EducationEntry:
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    graduation_year: Optional[int] = None   # only when the end year is a completed one
    ongoing: Optional[bool] = None          # True for "Present"/"Expected ..."
    gpa: Optional[str] = None
    raw_text: str = ""


@dataclass
class ExperienceEntry:
    organization: Optional[str] = None
    title: Optional[str] = None
    start_date: Optional[str] = None        # as written, e.g. "Jan 2021"
    end_date: Optional[str] = None          # as written, e.g. "Present"
    is_current: Optional[bool] = None
    description: List[str] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ProjectEntry:
    name: Optional[str] = None
    description: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)   # normalised taxonomy skills found in the entry
    raw_text: str = ""
    links: List[str] = field(default_factory=list)          # URLs written in the entry, as written


@dataclass
class CertificationEntry:
    name: Optional[str] = None
    issuer: Optional[str] = None
    year: Optional[int] = None
    kind: str = "certification"             # "certification" | "course"
    raw_text: str = ""


@dataclass
class TextProvenance:
    """Where a piece of extracted text came from.

    ``method`` is ``native_pdf``, ``native_docx``, ``native_text`` or ``ocr``.
    ``confidence`` is a Tesseract estimate when the method is OCR. It is not a
    guarantee that the text is correct. ``suppressed_duplicate`` is true when
    the text was kept for traceability but left out of the combined resume text.
    """
    page_number: Optional[int]
    method: str
    char_count: int
    confidence: Optional[float] = None
    suppressed_duplicate: bool = False


@dataclass
class QualityFinding:
    """One diagnostic statement about a resume file.

    ``kind`` is ``measured`` (a direct property), ``heuristic`` (a rule that can
    be wrong) or ``unsupported`` (something this phase does not decide).
    """
    code: str
    kind: str
    severity: str                               # "info" | "warning"
    message: str
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class QualityReport:
    findings: List[QualityFinding] = field(default_factory=list)
    measured: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)


@dataclass
class ResumeAnalysis:
    status: str = STATUS_FAILED
    source_format: str = "unknown"
    file_name: Optional[str] = None
    page_count: Optional[int] = None
    text_length: int = 0
    contact: ContactInfo = field(default_factory=ContactInfo)
    sections: List[Section] = field(default_factory=list)
    skills: List[DetectedSkill] = field(default_factory=list)
    education: List[EducationEntry] = field(default_factory=list)
    experience: List[ExperienceEntry] = field(default_factory=list)
    projects: List[ProjectEntry] = field(default_factory=list)
    certifications: List[CertificationEntry] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    # Phase 2 fields. Empty values are omitted by ``to_dict`` so Phase 1 JSON
    # stays the same for callers that never use document/OCR extraction.
    text_provenance: List[TextProvenance] = field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    schema_version: str = config.SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        if not data.get("text_provenance"):
            data.pop("text_provenance", None)
        if data.get("quality_report") is None:
            data.pop("quality_report", None)
        return data

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class JobRequirement:
    """One requirement taken from a job description.

    ``priority`` is required, preferred, or unspecified. A skill requirement
    stores the taxonomy name. Degree, certification, and experience fields are
    set only when the posting states them. Years are left empty when the
    posting does not give a number.
    """
    kind: str
    priority: str
    text: str
    section: Optional[str] = None
    skill_name: Optional[str] = None
    skill_category: Optional[str] = None
    degree_level: Optional[str] = None
    degree_field: Optional[str] = None
    certification_name: Optional[str] = None
    years_min: Optional[float] = None
    years_max: Optional[float] = None
    experience_status: Optional[str] = None
    # Set when the years apply to one skill, for example React in "2+ years with React".
    experience_focus: Optional[str] = None
    # When the posting says "A or B", every accepted name is listed. Empty means
    # ``skill_name`` is the only accepted skill. Evidence of any name satisfies it.
    alternatives: List[str] = field(default_factory=list)
    note: Optional[str] = None


@dataclass
class JobAnalysis:
    """Structured reading of a job description. No score is attached."""
    status: str = STATUS_FAILED
    source_format: str = "unknown"
    file_name: Optional[str] = None
    text_length: int = 0
    requirements: List[JobRequirement] = field(default_factory=list)
    sections: List[Section] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


@dataclass
class RequirementMatch:
    """How one job requirement compares with a resume.

    ``evidence`` is resume skill evidence and is required for a skill match.
    ``evidence_type`` is ``used`` or ``mentioned`` for a matched skill.
    ``support`` holds resume lines for a degree, certification, or dated
    experience match. ``related_skills`` are listed alternatives and do not
    make the outcome a match. ``satisfied_by`` is the accepted name that had
    resume evidence when a posting allows more than one.
    """
    requirement: JobRequirement
    outcome: str
    evidence_type: Optional[str] = None
    evidence: List[SkillEvidence] = field(default_factory=list)
    support: List[str] = field(default_factory=list)
    related_skills: List[str] = field(default_factory=list)
    note: Optional[str] = None
    satisfied_by: Optional[str] = None


@dataclass
class MatchReport:
    """Requirement-by-requirement comparison. Counts follow the outcomes.

    ``related_count`` is separate from ``matched_count``. Nothing here is an
    employability score or an ATS result.
    """
    status: str = STATUS_FAILED
    matches: List[RequirementMatch] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    reason: Optional[str] = None
    matched_count: int = 0
    related_count: int = 0
    missing_count: int = 0
    indeterminate_count: int = 0

    def __post_init__(self) -> None:
        self.matched_count = sum(item.outcome == OUTCOME_MATCHED for item in self.matches)
        self.related_count = sum(item.outcome == OUTCOME_RELATED for item in self.matches)
        self.missing_count = sum(item.outcome == OUTCOME_MISSING for item in self.matches)
        self.indeterminate_count = sum(item.outcome == OUTCOME_INDETERMINATE for item in self.matches)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
