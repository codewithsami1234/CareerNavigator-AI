"""Resume-intelligence pipeline: parsing -> cleaning -> sections -> skills/entities.

Public API
----------
``analyze_resume(file_path)``         Phase 1 PDF / DOCX / TXT file -> ``ResumeAnalysis``
                                      (scanned PDFs stay ``needs_ocr``; OCR is not run)
``analyze_text(text, source_format)`` already-extracted text -> ``ResumeAnalysis``
``analyze_document(file_path)``       Phase 2 path: native text, or OpenCV + Tesseract
                                      when the file is an image or the PDF page is sparse.
                                      The recovered text is passed to ``analyze_text``.
``analyze_job(text_or_path)``         pasted text or a PDF / DOCX / TXT job description
                                      -> ``JobAnalysis`` (no score)
``compare(resume, job)``              requirement outcomes: matched, related, missing,
                                      or indeterminate. Related is not a match.
``analyze_github(username_or_url)``   public GitHub profile metadata. Optional.
``career_report(resume, job, github)`` readiness estimate, skill gaps, roadmap,
                                      and evidence-based guidance. Guidance does not rescore.
                                      Resume-only calls stay valid.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from datetime import date
from typing import List, Optional, Union

import config
from extractors.entity_extractor import (
    extract_certifications, extract_contact, extract_education, extract_experience, extract_projects,
    without_link_lines,
)
from extractors.section_extractor import SectionExtractor
from extractors.skill_extractor import SkillExtractor
from parsers import parse_document
from schemas import (
    PARSE_OK, DocumentLink, JobAnalysis, MatchReport, ResumeAnalysis, STATUS_EMPTY, STATUS_FAILED,
    STATUS_NEEDS_OCR, STATUS_PARTIAL, STATUS_SUCCESS,
)
from utils.text_cleaner import has_meaningful_text, normalize_text

_CORE_SECTIONS = ("skills", "education", "experience")


@lru_cache(maxsize=4)
def _skill_extractor(taxonomy_path: Optional[str]) -> SkillExtractor:
    return SkillExtractor(taxonomy_path=taxonomy_path)


@lru_cache(maxsize=1)
def _section_extractor() -> SectionExtractor:
    return SectionExtractor()


def extract_skills(text: str, taxonomy_path: Union[str, Path, None] = None):
    """Clean ``text``, detect sections and return detected skills only.

    Unlike ``analyze_text`` this does not apply the "is this a whole document?" length gate, so it
    works on short snippets (used by the evaluation script and handy for experiments).
    """
    clean = normalize_text(text if isinstance(text, str) else "")
    sections = _section_extractor().extract(clean)
    return _skill_extractor(str(taxonomy_path) if taxonomy_path else None).extract(sections)


def analyze_text(
    text: str,
    source_format: str = "text",
    *,
    page_count: Optional[int] = None,
    file_name: Optional[str] = None,
    warnings: Optional[List[str]] = None,
    taxonomy_path: Union[str, Path, None] = None,
    links: Optional[List[DocumentLink]] = None,
) -> ResumeAnalysis:
    """Run the full extraction pipeline on already-extracted text.

    ``links`` are hyperlink targets stored in the file. They are used only to
    fill profile URLs whose visible text is a bare label such as ``GitHub``.
    """
    result = ResumeAnalysis(source_format=source_format, file_name=file_name, page_count=page_count,
                            warnings=list(warnings or []))
    if not isinstance(text, str):
        result.status = STATUS_FAILED
        result.errors.append("analyze_text expects a string.")
        return result

    try:
        clean = normalize_text(text)
        result.text_length = len(clean)
        if not has_meaningful_text(clean):
            result.status = STATUS_EMPTY
            result.warnings.append("No meaningful text was found, so nothing could be extracted.")
            return result

        sections = _section_extractor().extract(clean)
        skill_ex = _skill_extractor(str(taxonomy_path) if taxonomy_path else None)

        result.sections = sections
        result.contact = extract_contact(clean, sections, links=links)
        result.skills = skill_ex.extract(sections)
        result.education = extract_education(sections)
        result.experience = extract_experience(sections)
        result.projects = extract_projects(sections)
        for project in result.projects:
            project.technologies = skill_ex.find_in_text(without_link_lines(project.raw_text), "projects")
        result.certifications = extract_certifications(sections)
    except Exception as exc:   # never crash the caller; report instead
        result.status = STATUS_FAILED
        result.errors.append(f"Unexpected error while analysing the resume: {exc.__class__.__name__}: {exc}")
        return result

    names = {s.name for s in sections}
    detected = names - {"header"}
    if not detected:
        result.warnings.append(
            "No section headings were recognised, so only contact details and skills mentioned in the "
            "text could be extracted. Check data/section_aliases.json if headings use unusual names.")
    for core in _CORE_SECTIONS:
        if detected and core not in names:
            result.warnings.append(f"Section not detected: {core}.")
    if result.contact.email is None:
        result.warnings.append("No email address found.")
    if result.contact.phone is None:
        result.warnings.append("No phone number found.")
    if "education" in names and not result.education:
        result.warnings.append("An Education section was found but no degree or institution could be identified.")
    if "experience" in names and not result.experience:
        result.warnings.append("An Experience section was found but no job entries could be identified.")

    extracted_something = bool(result.skills or result.education or result.experience or result.projects
                               or result.certifications)
    result.status = STATUS_SUCCESS if (detected and extracted_something) else STATUS_PARTIAL
    return result


def analyze_resume(file_path: Union[str, Path], taxonomy_path: Union[str, Path, None] = None) -> ResumeAnalysis:
    """Parse a PDF, DOCX or TXT resume and extract structured information."""
    try:
        parsed = parse_document(file_path)
    except Exception as exc:
        return ResumeAnalysis(status=STATUS_FAILED,
                              errors=[f"Unexpected error while reading the file: {exc.__class__.__name__}: {exc}"])

    if parsed.status == STATUS_FAILED:
        return ResumeAnalysis(status=STATUS_FAILED, source_format=parsed.source_format,
                              file_name=parsed.file_name, page_count=parsed.page_count,
                              warnings=parsed.warnings, errors=parsed.errors)
    if parsed.status in (STATUS_NEEDS_OCR, STATUS_EMPTY):
        return ResumeAnalysis(status=parsed.status, source_format=parsed.source_format,
                              file_name=parsed.file_name, page_count=parsed.page_count,
                              warnings=parsed.warnings, errors=parsed.errors)

    return analyze_text(parsed.text, parsed.source_format, page_count=parsed.page_count,
                        file_name=parsed.file_name, warnings=parsed.warnings, taxonomy_path=taxonomy_path,
                        links=parsed.links)


def analyze_document(
    file_path: Union[str, Path],
    taxonomy_path: Union[str, Path, None] = None,
    *,
    ocr: bool = True,
    tesseract_cmd: Optional[str] = None,
    ocr_lang: Optional[str] = None,
):
    """Extract a PDF, DOCX, TXT, PNG or JPEG resume and run the Phase 1 analysers.

    Native text is used when a PDF page already has enough of it. Sparse pages
    and images are preprocessed with OpenCV and read with Tesseract when ``ocr``
    is true. Skill, section and entity extraction are the Phase 1 functions.
    This never raises for a bad file or a missing Tesseract installation.
    """
    from extraction.unified import extract_document, provenance_of
    from ocr.tesseract_ocr import OcrSettings

    try:
        extracted = extract_document(
            file_path,
            ocr=ocr,
            settings=OcrSettings(tesseract_cmd=tesseract_cmd, lang=ocr_lang),
        )
    except Exception as exc:
        return ResumeAnalysis(
            status=STATUS_FAILED,
            errors=[f"Unexpected error while reading the file: {exc.__class__.__name__}: {exc}"],
        )

    provenance = provenance_of(extracted)
    if extracted.status != PARSE_OK:
        return ResumeAnalysis(
            status=extracted.status,
            source_format=extracted.source_format,
            file_name=extracted.file_name,
            page_count=extracted.page_count,
            warnings=list(extracted.warnings),
            errors=list(extracted.errors),
            text_provenance=provenance,
            quality_report=extracted.quality,
        )

    analysis = analyze_text(
        extracted.text,
        extracted.source_format,
        page_count=extracted.page_count,
        file_name=extracted.file_name,
        warnings=extracted.warnings,
        taxonomy_path=taxonomy_path,
        links=extracted.links,
    )
    analysis.errors.extend(extracted.errors)
    analysis.text_provenance = provenance
    analysis.quality_report = extracted.quality
    return analysis


def analyze_job(text_or_path: Union[str, Path, None], taxonomy_path: Union[str, Path, None] = None) -> JobAnalysis:
    """Read a pasted job description or a PDF, DOCX, or TXT file.

    Required and preferred come from headings and from explicit words on the
    line. When those are missing or they disagree, the priority is unspecified.
    The result has no employability score and makes no ATS claim.
    """
    from job_analysis.parser import prepare_job
    from job_analysis.requirements import extract_requirements

    job = prepare_job(text_or_path)
    if job.status != PARSE_OK:
        return job
    try:
        extractor = _skill_extractor(str(taxonomy_path) if taxonomy_path else None)
        job.requirements = extract_requirements(job.sections, extractor)
    except Exception as exc:
        job.status = STATUS_FAILED
        job.reason = f"Unexpected error while reading the job description: {exc.__class__.__name__}: {exc}"
        job.errors.append(job.reason)
        return job
    if job.requirements:
        job.status = STATUS_SUCCESS
        job.reason = None
        return job
    job.status = STATUS_PARTIAL
    job.reason = "No requirements could be identified."
    if job.reason not in job.warnings:
        job.warnings.append(job.reason)
    return job


def compare(resume: ResumeAnalysis, job: JobAnalysis, *, as_of: Optional[date] = None) -> MatchReport:
    """Compare resume evidence with job requirements.

    Outcomes are matched, related, missing, or indeterminate. A related skill
    is a listed alternative, not every skill in the same category, and is not
    a match. ``as_of`` is the date used when a resume job ends with Present.
    Proficiency is not inferred.
    """
    from job_analysis.matcher import compare_requirements

    return compare_requirements(resume, job, as_of=as_of)


def analyze_github(username_or_url: str, **kwargs):
    """Read public GitHub metadata. Network errors stay inside the returned object."""
    from github_analysis import analyze_github as _analyze_github

    return _analyze_github(username_or_url, **kwargs)


def career_report(resume: ResumeAnalysis, job: Optional[JobAnalysis] = None, github=None, *,
                  as_of: Optional[date] = None, weekly_hours: Optional[int] = None):
    """Run comparison, readiness, recommendations, and a roadmap without re-parsing.

    A missing job or a failed GitHub read does not discard ``resume``.
    """
    from dataclasses import dataclass, field
    from typing import Any, Dict

    from assessment.guidance import build_guidance
    from assessment.readiness import assess_readiness
    from assessment.recommendations import recommend_gaps
    from assessment.roadmap import build_roadmap

    comparison = compare(resume, job, as_of=as_of) if job is not None else None
    readiness = assess_readiness(resume, job if job is not None else None, comparison, github)
    evidenced = [
        skill.name for skill in getattr(resume, "skills", []) or []
        if getattr(skill, "name", None) and getattr(skill, "evidence", None)
    ]
    recommendations = recommend_gaps(
        job if job is not None else None, comparison, evidenced_skills=evidenced,
    )
    roadmap = build_roadmap(recommendations, weekly_hours=weekly_hours)
    guidance = build_guidance(
        resume,
        job if job is not None else None,
        comparison,
        recommendations,
        roadmap,
        github,
        weekly_hours=weekly_hours,
    )
    github_status = None if github is None else getattr(github, "status", None)
    limitations = [
        "Resume analysis does not require GitHub or a job description.",
        "The readiness number is an evidence-based estimate, not a hiring prediction and not an ATS score.",
    ]
    if github is None:
        limitations.append("GitHub analysis was not requested.")
    elif github_status not in (None, STATUS_SUCCESS):
        limitations.append("GitHub analysis was unavailable. Resume and job results are unchanged.")

    @dataclass
    class CareerReport:
        resume_status: str
        comparison: Optional[MatchReport]
        github_status: Optional[str]
        readiness: Any
        recommendations: Any
        roadmap: Any
        guidance: Any
        limitations: list = field(default_factory=list)

        def to_dict(self) -> Dict[str, Any]:
            def dump(value):
                if value is None:
                    return None
                if hasattr(value, "to_dict"):
                    return value.to_dict()
                return value

            return {
                "resume_status": self.resume_status,
                "comparison": dump(self.comparison),
                "github_status": self.github_status,
                "readiness": dump(self.readiness),
                "recommendations": dump(self.recommendations),
                "roadmap": dump(self.roadmap),
                "guidance": dump(self.guidance),
                "limitations": list(self.limitations),
            }

    return CareerReport(
        resume_status=resume.status,
        comparison=comparison,
        github_status=github_status,
        readiness=readiness,
        recommendations=recommendations,
        roadmap=roadmap,
        guidance=guidance,
        limitations=limitations,
    )
