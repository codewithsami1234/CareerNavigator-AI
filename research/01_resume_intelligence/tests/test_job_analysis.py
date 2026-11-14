"""Job-description reading and comparison. All postings and resumes here are synthetic."""
from datetime import date
from pathlib import Path

import sample_data as sd
from pipeline import analyze_job, analyze_text, compare
from web.view_model import comparison_groups
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED,
    PRIORITY_PREFERRED, PRIORITY_REQUIRED, PRIORITY_UNSPECIFIED, REQUIREMENT_CERTIFICATION,
    REQUIREMENT_DEGREE, REQUIREMENT_EXPERIENCE, REQUIREMENT_SKILL, STATUS_EMPTY, STATUS_FAILED,
    STATUS_NEEDS_OCR, STATUS_PARTIAL, STATUS_SUCCESS, CertificationEntry, DetectedSkill,
    EducationEntry, ExperienceEntry, JobAnalysis, MatchReport, ProjectEntry, RequirementMatch,
    ResumeAnalysis, SkillEvidence,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AS_OF = date(2026, 10, 17)


def _one(items, **kwargs):
    hits = [item for item in items if all(getattr(item, key) == value for key, value in kwargs.items())]
    assert len(hits) == 1, (kwargs, [(getattr(item, "kind", None), getattr(item, "skill_name", None),
                                      getattr(item, "priority", None), getattr(item, "text", None))
                                     for item in items])
    return hits[0]


def _requirement(job, **kwargs):
    return _one(job.requirements, **kwargs)


def _match(report, **kwargs):
    hits = [
        item for item in report.matches
        if all(getattr(item.requirement, key) == value for key, value in kwargs.items())
    ]
    assert len(hits) == 1, (kwargs, [
        (item.outcome, item.requirement.kind, item.requirement.skill_name, item.requirement.experience_focus,
         item.requirement.degree_level, item.requirement.degree_field, item.requirement.text)
        for item in report.matches
    ])
    return hits[0]


def _resume(**kwargs) -> ResumeAnalysis:
    data = dict(status=STATUS_SUCCESS, source_format="text", text_length=80)
    data.update(kwargs)
    return ResumeAnalysis(**data)


def _skill(name, category, evidence_type, line, section):
    return DetectedSkill(
        name=name, category=category, evidence_type=evidence_type, mention_count=1,
        matched_as=[name],
        evidence=[SkillEvidence(section=section, text=line, evidence_type=evidence_type, matched_as=name)],
    )


class TestEmptyAndUnreadable:
    def test_empty_text(self):
        for text in ("", "   \n\t", "!!! ??? ### $$$"):
            job = analyze_job(text)
            assert job.status == STATUS_EMPTY
            assert job.requirements == []
            assert job.reason
            assert job.errors == []

    def test_non_text_input_fails(self):
        job = analyze_job(None)
        assert job.status == STATUS_FAILED
        assert job.reason
        assert job.requirements == []

    def test_missing_file(self, tmp_path):
        job = analyze_job(tmp_path / "missing-job.pdf")
        assert job.status == STATUS_FAILED
        assert job.requirements == []
        assert any("not found" in error.lower() for error in job.errors)
        assert job.reason

    def test_malformed_pdf(self):
        job = analyze_job(FIXTURES / "malformed.pdf")
        assert job.status == STATUS_FAILED
        assert job.errors
        assert job.requirements == []

    def test_image_only_pdf_needs_text(self):
        job = analyze_job(FIXTURES / "image_only_scan_like.pdf")
        assert job.status == STATUS_NEEDS_OCR
        assert job.reason
        assert job.requirements == []

    def test_multiline_text_is_not_a_file_path(self):
        job = analyze_job(
            "Please review job.pdf before applying.\n"
            "- Python is required for this backend role.\n"
        )
        assert job.status == STATUS_SUCCESS
        assert _requirement(job, kind=REQUIREMENT_SKILL, skill_name="Python").priority == PRIORITY_REQUIRED

    def test_short_text_file_is_still_read(self, tmp_path):
        path = tmp_path / "role.txt"
        path.write_text("Requirements\n- Python\n", encoding="utf-8")
        job = analyze_job(path)
        assert job.status == STATUS_SUCCESS
        assert job.file_name == "role.txt"
        assert job.source_format == "text"
        requirement = _requirement(job, kind=REQUIREMENT_SKILL, skill_name="Python")
        assert requirement.priority == PRIORITY_REQUIRED


class TestGarbledAndHeadings:
    def test_garbled_text_identifies_nothing(self):
        job = analyze_job("asdf qwer zxcv plugh xyzzy " * 8)
        assert job.status == STATUS_PARTIAL
        assert job.requirements == []
        assert job.reason == "No requirements could be identified."

    def test_missing_headings_use_wording_only(self):
        job = analyze_job(
            "The team uses Docker for local setups in this role and writes services daily.\n"
            "Python is required for this backend position and the services around it.\n"
            "Kubernetes would be a plus for the deployment work described here today.\n"
        )
        assert job.status == STATUS_SUCCESS
        assert any("headings" in warning.lower() for warning in job.warnings)
        assert _requirement(job, skill_name="Docker").priority == PRIORITY_UNSPECIFIED
        assert _requirement(job, skill_name="Python").priority == PRIORITY_REQUIRED
        assert _requirement(job, skill_name="Kubernetes").priority == PRIORITY_PREFERRED

    def test_inline_heading_keeps_the_listed_skills_required(self):
        job = analyze_job("Requirements: Python and SQL")
        assert _requirement(job, skill_name="Python").priority == PRIORITY_REQUIRED
        assert _requirement(job, skill_name="SQL").priority == PRIORITY_REQUIRED

    def test_experience_heading_does_not_inherit_requirements(self):
        job = analyze_job(
            "Requirements\n"
            "- Python\n"
            "\n"
            "Experience\n"
            "- 5 years of experience building APIs.\n"
        )
        assert _requirement(job, skill_name="Python").priority == PRIORITY_REQUIRED
        years = _requirement(job, kind=REQUIREMENT_EXPERIENCE)
        assert years.section == "background"
        assert years.priority == PRIORITY_UNSPECIFIED
        assert years.years_min == 5
        assert years.experience_status == "stated"

    def test_high_school_diploma_is_not_turned_into_a_degree(self):
        job = analyze_job("Requirements\n- High school diploma required\n")
        assert job.status == STATUS_PARTIAL
        assert [item.kind for item in job.requirements if item.kind == REQUIREMENT_DEGREE] == []


class TestPriorities:
    def test_heading_sets_required_and_preferred(self):
        job = analyze_job(
            "Required qualifications\n"
            "- SQL\n"
            "\n"
            "Nice to have\n"
            "- Docker\n"
            "\n"
            "Responsibilities\n"
            "- Build services with Java.\n"
        )
        assert _requirement(job, skill_name="SQL").priority == PRIORITY_REQUIRED
        assert _requirement(job, skill_name="Docker").priority == PRIORITY_PREFERRED
        assert _requirement(job, skill_name="Java").priority == PRIORITY_UNSPECIFIED

    def test_heading_and_line_disagree(self):
        job = analyze_job(
            "Preferred qualifications\n"
            "- Python is required for the backend services on this team.\n"
        )
        requirement = _requirement(job, skill_name="Python")
        assert requirement.priority == PRIORITY_UNSPECIFIED
        assert "disagree" in (requirement.note or "").lower() or "both" in (requirement.note or "").lower()

    def test_one_line_with_both_labels_stays_unspecified(self):
        job = analyze_job(
            "Requirements\n"
            "- Python is required and Docker is a plus for deployment.\n"
        )
        assert _requirement(job, skill_name="Python").priority == PRIORITY_UNSPECIFIED
        assert _requirement(job, skill_name="Docker").priority == PRIORITY_UNSPECIFIED

    def test_link_line_is_not_a_skill(self):
        job = analyze_job(
            "Requirements\n"
            "- GitHub: https://github.com/example/demo\n"
            "- Python\n"
        )
        assert [item.skill_name for item in job.requirements if item.kind == REQUIREMENT_SKILL] == ["Python"]

    def test_repeated_skill_with_two_labels_is_unspecified(self):
        job = analyze_job("Requirements\n- Python\n\nPreferred\n- Python\n")
        requirement = _requirement(job, skill_name="Python")
        assert requirement.priority == PRIORITY_UNSPECIFIED
        assert "more than one way" in (requirement.note or "")


class TestSkillComparison:
    def test_used_and_mentioned_stay_distinct_and_need_evidence(self):
        resume = _resume(skills=[
            _skill("Python", "Programming Languages", "used", "Built a Python API.", "projects"),
            _skill("SQL", "Databases", "mentioned", "SQL", "skills"),
            DetectedSkill(name="Java", category="Programming Languages", evidence_type="mentioned",
                          mention_count=1, evidence=[]),
        ])
        job = analyze_job("Requirements\n- Python\n- SQL\n- Java\n- Kubernetes\n")
        report = compare(resume, job)
        used = _match(report, skill_name="Python")
        mentioned = _match(report, skill_name="SQL")
        empty = _match(report, skill_name="Java")
        absent = _match(report, skill_name="Kubernetes")

        assert used.outcome == OUTCOME_MATCHED and used.evidence and used.evidence_type == "used"
        assert used.evidence[0].text == "Built a Python API."
        assert mentioned.outcome == OUTCOME_MATCHED and mentioned.evidence_type == "mentioned"
        assert "proficiency is not inferred" in mentioned.note.lower()
        assert empty.outcome == OUTCOME_MISSING and empty.evidence == []
        assert absent.outcome == OUTCOME_MISSING
        assert "proficiency" not in RequirementMatch.__dataclass_fields__
        assert "score" not in MatchReport.__dataclass_fields__

    def test_related_skill_is_not_a_match(self):
        resume = _resume(skills=[
            _skill("TensorFlow", "AI and Machine Learning", "used", "Trained models with TensorFlow.", "projects"),
            _skill("Python", "Programming Languages", "mentioned", "Python", "skills"),
        ])
        job = analyze_job("Requirements\n- PyTorch\n")
        report = compare(resume, job)
        match = _match(report, skill_name="PyTorch")
        assert match.outcome == OUTCOME_RELATED
        assert match.related_skills == ["TensorFlow"]
        assert match.evidence == [] and match.evidence_type is None
        assert report.matched_count == 0
        assert report.related_count == 1
        assert report.matched_count == sum(item.outcome == OUTCOME_MATCHED for item in report.matches)

    def test_sql_category_comes_from_the_taxonomy(self):
        job = analyze_job("Requirements\n- SQL\n")
        assert _requirement(job, skill_name="SQL").skill_category == "Databases"


class TestDegreesAndCertifications:
    def test_degree_field_certification_and_phd(self):
        job = analyze_job(
            "Requirements\n"
            "- Bachelor's degree in Information Technology\n"
            "- PhD in Computer Science\n"
            "- Google Data Analytics Professional Certificate\n"
        )
        bachelor = _requirement(job, degree_level="bachelor")
        phd = _requirement(job, degree_level="doctorate")
        cert = _requirement(job, kind=REQUIREMENT_CERTIFICATION)
        assert bachelor.degree_field == "Information Technology"
        assert bachelor.priority == PRIORITY_REQUIRED
        assert phd.degree_field == "Computer Science"
        assert "Google Data Analytics" in cert.certification_name

    def test_degree_match_field_mismatch_and_higher_level(self):
        resume = _resume(education=[
            EducationEntry(degree="Bachelor of Science", field_of_study="Information Technology",
                           raw_text="Bachelor of Science in Information Technology, Example University"),
        ])
        job = analyze_job(
            "Requirements\n"
            "- Bachelor's degree in Information Technology\n"
            "- Bachelor's degree in Mechanical Engineering\n"
            "- Master's degree\n"
        )
        report = compare(resume, job)
        assert _match(report, degree_field="Information Technology").outcome == OUTCOME_MATCHED
        assert "Example University" in _match(report, degree_field="Information Technology").support[0]
        assert _match(report, degree_field="Mechanical Engineering").outcome == OUTCOME_MISSING
        assert _match(report, degree_level="master", degree_field=None).outcome == OUTCOME_MISSING

    def test_masters_degree_does_not_satisfy_a_bachelors_requirement(self):
        resume = _resume(education=[
            EducationEntry(
                degree="Master of Science", field_of_study="Computer Science",
                raw_text="Master of Science in Computer Science, Example University",
            ),
        ])
        job = analyze_job("Requirements\n- Bachelor's degree\n")
        match = _match(compare(resume, job), degree_level="bachelor")
        assert match.outcome == OUTCOME_MISSING
        assert match.support == []
        assert "different level" in (match.note or "").lower()

    def test_missing_field_is_indeterminate(self):
        resume = _resume(education=[
            EducationEntry(degree="Bachelor of Science", field_of_study=None, raw_text="Bachelor of Science"),
        ])
        job = analyze_job("Requirements\n- Bachelor's degree in Computer Science\n")
        match = _match(compare(resume, job), degree_level="bachelor")
        assert match.outcome == OUTCOME_INDETERMINATE
        assert match.support == []

    def test_degree_without_a_required_field_matches_the_level(self):
        resume = _resume(education=[
            EducationEntry(degree="Bachelor of Science", field_of_study=None, raw_text="Bachelor of Science"),
        ])
        job = analyze_job("Requirements\n- Bachelor's degree\n")
        match = _match(compare(resume, job), degree_level="bachelor")
        assert match.outcome == OUTCOME_MATCHED
        assert match.support

    def test_certification_match_miss_and_unnamed(self):
        resume = _resume(certifications=[
            CertificationEntry(name="Google Data Analytics Professional Certificate",
                               raw_text="Google Data Analytics Professional Certificate - Coursera (2023)"),
        ])
        job = analyze_job(
            "Requirements\n"
            "- Google Data Analytics Professional Certificate\n"
            "- AWS Certified Solutions Architect\n"
        )
        report = compare(resume, job)
        google = next(item for item in report.matches if "Google" in (item.requirement.certification_name or ""))
        aws = next(item for item in report.matches if "AWS" in (item.requirement.certification_name or ""))
        assert google.outcome == OUTCOME_MATCHED and "Coursera" in google.support[0]
        assert aws.outcome == OUTCOME_MISSING

        unnamed = _resume(certifications=[CertificationEntry(name=None, raw_text="certificate on file")])
        unnamed_job = analyze_job("Requirements\n- AWS Certified Solutions Architect\n")
        assert _match(compare(unnamed, unnamed_job), kind=REQUIREMENT_CERTIFICATION).outcome == OUTCOME_INDETERMINATE


class TestExperience:
    def _job(self, line: str) -> JobAnalysis:
        return analyze_job(f"Requirements\n- {line}\n")

    def test_stated_range_and_vague_duration(self):
        stated = _requirement(self._job("3-5 years of experience"), kind=REQUIREMENT_EXPERIENCE)
        assert stated.years_min == 3 and stated.years_max == 5 and stated.experience_status == "stated"
        vague = _requirement(self._job("several years of experience in industry"), kind=REQUIREMENT_EXPERIENCE)
        assert vague.years_min is None and vague.experience_status == "indeterminate"
        python = self._job("at least 2 years of Python experience")
        assert _requirement(python, kind=REQUIREMENT_EXPERIENCE).years_min == 2
        assert _requirement(python, skill_name="Python").priority == PRIORITY_REQUIRED
        mixed = _requirement(
            self._job("3 years of experience or 5 years of experience"), kind=REQUIREMENT_EXPERIENCE,
        )
        assert mixed.years_min is None and mixed.experience_status == "indeterminate"
        possessive = _requirement(self._job("3 years' experience"), kind=REQUIREMENT_EXPERIENCE)
        assert possessive.years_min == 3 and possessive.experience_status == "stated"

    def test_explicit_dates_match_or_fall_short(self):
        long_resume = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="Jan 2010",
                            end_date="Jan 2020", raw_text="Developer, Demo Ltd (Jan 2010 - Jan 2020)"),
        ])
        short_resume = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="Jan 2024",
                            end_date="Mar 2024", raw_text="Developer, Demo Ltd (Jan 2024 - Mar 2024)"),
        ])
        job = self._job("5 years of experience")
        matched = _match(compare(long_resume, job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE)
        missing = _match(compare(short_resume, job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE)
        assert matched.outcome == OUTCOME_MATCHED and matched.support
        assert missing.outcome == OUTCOME_MISSING and missing.support
        assert "score" not in (matched.note or "").lower()

    def test_present_uses_the_supplied_date(self):
        resume = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="Jan 2022",
                            end_date="Present", is_current=True,
                            raw_text="Developer, Demo Ltd (Jan 2022 - Present)"),
        ])
        job = self._job("3 years of experience")
        assert _match(compare(resume, job, as_of=date(2026, 1, 1)), kind=REQUIREMENT_EXPERIENCE).outcome == OUTCOME_MATCHED

    def test_ambiguous_and_missing_dates_are_indeterminate(self):
        ambiguous = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="early 2020",
                            end_date="Present", raw_text="Developer, Demo Ltd (early 2020 - Present)"),
        ])
        undated = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="Jan 2024",
                            end_date="Mar 2024", raw_text="Developer, Demo Ltd (Jan 2024 - Mar 2024)"),
            ExperienceEntry(title="Analyst", organization="Other Ltd", raw_text="Analyst, Other Ltd"),
        ])
        empty = _resume(experience=[])
        job = self._job("5 years of experience")
        vague_job = self._job("several years of experience")
        long_resume = _resume(experience=[
            ExperienceEntry(title="Developer", organization="Demo Ltd", start_date="Jan 2010",
                            end_date="Jan 2020", raw_text="Developer, Demo Ltd (Jan 2010 - Jan 2020)"),
        ])
        assert _match(compare(ambiguous, job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE).outcome == OUTCOME_INDETERMINATE
        assert _match(compare(undated, job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE).outcome == OUTCOME_INDETERMINATE
        assert _match(compare(empty, job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE).outcome == OUTCOME_INDETERMINATE
        vague = _match(compare(long_resume, vague_job, as_of=AS_OF), kind=REQUIREMENT_EXPERIENCE)
        assert vague.outcome == OUTCOME_INDETERMINATE
        assert "number of years" in (vague.note or "").lower() or "does not state" in (vague.note or "").lower()

    def test_duration_warning_does_not_invent_a_score(self):
        resume = _resume(experience=[
            ExperienceEntry(start_date="Jan 2010", end_date="Jan 2020", raw_text="Jan 2010 - Jan 2020"),
        ])
        report = compare(resume, self._job("5 years of experience"), as_of=AS_OF)
        assert any("overlapping" in warning.lower() for warning in report.warnings)
        assert "ats" not in report.to_json().lower()

    def test_overlapping_six_year_jobs_are_added_toward_ten_years(self):
        """Dated jobs are summed. Overlap is warned about and is not removed."""
        resume = _resume(experience=[
            ExperienceEntry(
                title="Developer", organization="One Ltd",
                start_date="Jan 2018", end_date="Jan 2024",
                raw_text="Developer, One Ltd (Jan 2018 - Jan 2024)",
            ),
            ExperienceEntry(
                title="Developer", organization="Two Ltd",
                start_date="Jan 2020", end_date="Jan 2026",
                raw_text="Developer, Two Ltd (Jan 2020 - Jan 2026)",
            ),
        ])
        report = compare(resume, self._job("10 years of experience"), as_of=AS_OF)
        match = _match(report, kind=REQUIREMENT_EXPERIENCE)
        assert match.outcome == OUTCOME_MATCHED
        assert len(match.support) == 2
        assert "One Ltd" in match.support[0] or any("One Ltd" in line for line in match.support)
        assert any("Two Ltd" in line for line in match.support)
        assert "overlapping" in (match.note or "").lower()
        assert any("overlapping" in warning.lower() for warning in report.warnings)
        assert "ats" not in report.to_json().lower()


class TestCompareGuards:
    def test_empty_or_failed_inputs_are_not_compared(self):
        resume = _resume()
        empty = compare(resume, analyze_job(""))
        assert empty.status == STATUS_EMPTY and empty.matches == [] and empty.reason
        failed = compare(_resume(status=STATUS_FAILED, errors=["File not found."]), analyze_job("Requirements\n- Python\n"))
        assert failed.status == STATUS_FAILED and failed.matches == []
        assert compare(resume, "not a job").status == STATUS_FAILED
        assert compare(resume, analyze_job("Requirements\n- Python\n"), as_of="today").status == STATUS_FAILED

    def test_counts_follow_outcomes(self):
        report = MatchReport(status=STATUS_SUCCESS, matches=[
            RequirementMatch(
                requirement=_requirement(analyze_job("Requirements\n- Python\n"), skill_name="Python"),
                outcome=OUTCOME_RELATED, related_skills=["Java"],
            ),
        ], matched_count=99)
        assert report.matched_count == 0
        assert report.related_count == 1

    def test_resume_schema_has_no_job_fields(self):
        assert "requirements" not in ResumeAnalysis.__dataclass_fields__
        assert "matched_count" not in ResumeAnalysis.__dataclass_fields__


class TestPipelineResume:
    def test_synthetic_resume_against_a_posting(self):
        resume = analyze_text(sd.FULL_RESUME, "text")
        assert resume.status == STATUS_SUCCESS
        job = analyze_job(
            "Requirements\n"
            "- Python\n"
            "- SQL\n"
            "- Kubernetes\n"
            "- Pygame\n"
            "- Bachelor's degree in Information Technology\n"
            "- Google Data Analytics Professional Certificate\n"
            "- 3 years of experience\n"
            "\n"
            "Preferred\n"
            "- Docker\n"
            "- PyTorch\n"
        )
        assert job.status == STATUS_SUCCESS
        report = compare(resume, job, as_of=AS_OF)
        assert report.status == STATUS_SUCCESS
        assert _match(report, skill_name="Python").outcome == OUTCOME_MATCHED
        assert _match(report, skill_name="Python").evidence_type == "used"
        assert _match(report, skill_name="Python").evidence
        assert _match(report, skill_name="SQL").evidence_type == "mentioned"
        kubernetes = _match(report, skill_name="Kubernetes")
        assert kubernetes.outcome == OUTCOME_RELATED
        assert "Docker" in kubernetes.related_skills
        assert "Python" not in kubernetes.related_skills
        assert _match(report, skill_name="Pygame").outcome == OUTCOME_MISSING
        docker = _match(report, skill_name="Docker")
        assert docker.requirement.priority == PRIORITY_PREFERRED and docker.outcome == OUTCOME_MATCHED
        pytorch = _match(report, skill_name="PyTorch")
        assert pytorch.outcome == OUTCOME_RELATED and pytorch.evidence == []
        assert "Python" not in pytorch.related_skills and pytorch.related_skills
        assert _match(report, degree_level="bachelor").outcome == OUTCOME_MATCHED
        google = next(item for item in report.matches if item.requirement.kind == REQUIREMENT_CERTIFICATION)
        assert google.outcome == OUTCOME_MATCHED
        assert _match(report, kind=REQUIREMENT_EXPERIENCE).outcome == OUTCOME_MATCHED
        assert report.related_count == sum(item.outcome == OUTCOME_RELATED for item in report.matches)
        assert "employability" not in report.to_json().lower()
        assert job.to_dict()["requirements"]


FRONTEND_POSTING = """
Frontend Developer (React)

About the company
We are a fast-growing product company. Our stack includes TypeScript, Docker, and GitLab.
Join us and learn CI/CD and Microsoft Azure on the job.

Benefits
- Competitive salary and health insurance
- Learn Redux, TypeScript, and Docker on the job

Requirements
- 3+ years of professional software development experience, including 2+ years with React
- Strong proficiency in JavaScript, including React hooks, TypeScript, and modern JavaScript (ES6+)
- Experience with Flux or Redux or similar state-management approaches
- Understanding of functional programming principles
- Experience consuming REST APIs
- Familiarity with Git

Preferred
- GitLab
- Docker and CI/CD
"""

FRONTEND_RESUME = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
JavaScript, React.js, CSS, Git, GitHub, Node.js, C++

PROJECTS

Library System | C++
- Console library built with object-oriented programming

Puzzle Game | React.js, CSS, JavaScript
- Interactive browser puzzle

Notes App | Node.js
- Stores notes for a class assignment
"""


class TestRequirementGaps:
    """Explicit requirements stay missing when the resume only has a nearby skill."""

    def test_posting_that_requires_only_python(self):
        job = analyze_job("Requirements\n- Python\n")
        assert [item.skill_name for item in job.requirements] == ["Python"]
        assert job.requirements[0].priority == PRIORITY_REQUIRED
        assert job.requirements[0].text

        present = _resume(skills=[
            _skill("Python", "Programming Languages", "used", "Built services in Python.", "projects"),
        ])
        matched = _match(compare(present, job), skill_name="Python")
        assert matched.outcome == OUTCOME_MATCHED
        assert matched.evidence and "Python" in matched.evidence[0].text

        absent = _resume(skills=[
            _skill("Java", "Programming Languages", "mentioned", "Java", "skills"),
        ])
        missing = _match(compare(absent, job), skill_name="Python")
        assert missing.outcome == OUTCOME_MISSING
        assert missing.evidence == [] and missing.related_skills == []
        assert "Python" in missing.requirement.text

    def test_nearby_skills_are_not_exact_matches(self):
        cases = [
            ("TypeScript", "JavaScript", "Programming Languages", "JavaScript"),
            ("GitLab", "GitHub", "Development Tools", "GitHub"),
            ("REST API", "Node.js", "Backend Development", "Built a Node.js service."),
            ("Docker", "Microsoft Azure", "Cloud and DevOps", "Microsoft Azure"),
            ("CI/CD", "Microsoft Azure", "Cloud and DevOps", "Microsoft Azure"),
        ]
        for required, present, category, line in cases:
            resume = _resume(skills=[_skill(present, category, "mentioned", line, "skills")])
            job = analyze_job(f"Requirements\n- {required}\n")
            match = _match(compare(resume, job), skill_name=required)
            assert match.outcome == OUTCOME_MISSING, required
            assert present not in match.related_skills
            assert match.evidence == []
            assert required in (match.requirement.text or "")

    def test_frontend_posting_does_not_hide_missing_requirements(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        assert resume.status == STATUS_SUCCESS
        assert any(skill.name == "React" for skill in resume.skills)
        assert any(skill.name == "Object-Oriented Programming" for skill in resume.skills)
        assert resume.experience == []

        job = analyze_job(FRONTEND_POSTING)
        assert job.status == STATUS_SUCCESS
        names = [item.skill_name for item in job.requirements if item.kind == REQUIREMENT_SKILL]
        assert names.count("TypeScript") == 1
        assert "Microsoft Azure" not in names
        typescript = _requirement(job, skill_name="TypeScript")
        assert typescript.priority == PRIORITY_REQUIRED
        assert "on the job" not in typescript.text.lower()
        assert "stack" not in typescript.text.lower()
        alternatives = _requirement(job, skill_name="Flux")
        assert alternatives.priority == PRIORITY_REQUIRED
        assert alternatives.alternatives == ["Flux", "Redux", "state management"]
        assert "on the job" not in alternatives.text.lower()
        assert "Flux" in alternatives.text and "Redux" in alternatives.text
        hooks = _requirement(job, skill_name="React hooks")
        assert hooks.text == "React hooks"
        assert hooks.alternatives == []
        assert _requirement(job, skill_name="JavaScript").skill_name != hooks.skill_name
        assert _requirement(job, skill_name="functional programming").priority == PRIORITY_REQUIRED
        posting_text = " ".join(item.text.lower() for item in job.requirements)
        assert "health insurance" not in posting_text
        assert "fast-growing" not in posting_text
        assert "competitive salary" not in posting_text

        general = _requirement(job, kind=REQUIREMENT_EXPERIENCE, years_min=3)
        react_years = _requirement(job, kind=REQUIREMENT_EXPERIENCE, years_min=2, experience_focus="React")
        assert general.experience_focus is None
        assert "3+" in general.text or "3 +" in general.text
        assert "React" in react_years.text

        report = compare(resume, job, as_of=AS_OF)
        assert report.status == STATUS_SUCCESS
        assert report.missing_count > 0

        def outcome(skill_name):
            return _match(report, skill_name=skill_name)

        assert outcome("JavaScript").outcome == OUTCOME_MATCHED
        assert outcome("JavaScript").evidence and "JavaScript" in outcome("JavaScript").evidence[0].text
        assert outcome("Git").outcome == OUTCOME_MATCHED and outcome("Git").evidence
        assert outcome("React").outcome == OUTCOME_MATCHED and outcome("React").evidence
        assert "year" not in (outcome("React").requirement.text or "").lower()
        assert not any(
            item.kind == REQUIREMENT_SKILL and "year" in (item.text or "").lower()
            for item in job.requirements
        )

        for skill_name in (
            "TypeScript", "React hooks", "Flux",
            "functional programming", "REST API", "GitLab", "Docker", "CI/CD",
        ):
            match = outcome(skill_name)
            assert match.outcome == OUTCOME_MISSING, skill_name
            assert match.evidence == []
            assert match.requirement.text.strip()
            assert match.requirement.priority in (PRIORITY_REQUIRED, PRIORITY_PREFERRED)

        assert "JavaScript" not in outcome("TypeScript").related_skills
        assert "React" not in outcome("React hooks").related_skills
        assert "React" not in outcome("Flux").related_skills
        assert outcome("Flux").requirement.alternatives == ["Flux", "Redux", "state management"]
        assert "Node.js" not in outcome("REST API").related_skills
        assert "GitHub" not in outcome("GitLab").related_skills
        assert outcome("Docker").requirement.priority == PRIORITY_PREFERRED
        assert outcome("GitLab").requirement.priority == PRIORITY_PREFERRED

        for item in report.matches:
            if item.requirement.kind != REQUIREMENT_EXPERIENCE:
                continue
            assert item.outcome == OUTCOME_INDETERMINATE
            assert item.requirement.text.strip()
            note = (item.note or "").lower()
            assert "unverif" in note or "insufficient" in note
            assert "project" in note
        assert _match(report, kind=REQUIREMENT_EXPERIENCE, experience_focus="React").outcome == OUTCOME_INDETERMINATE
        assert _match(report, kind=REQUIREMENT_EXPERIENCE, years_min=3).outcome == OUTCOME_INDETERMINATE

        for item in report.matches:
            if item.outcome == OUTCOME_MATCHED:
                support = [entry.text for entry in item.evidence if entry.text] + [line for line in item.support if line]
                assert support
            else:
                assert item.requirement.text.strip()
        assert "employability" not in report.to_json().lower()
        assert "score" not in report.to_json().lower()

    def test_or_group_is_satisfied_by_either_alternative(self):
        job = analyze_job("Requirements\n- Experience with Flux or Redux\n")
        requirement = _requirement(job, skill_name="Flux")
        assert requirement.alternatives == ["Flux", "Redux"]
        assert [item.skill_name for item in job.requirements if item.kind == REQUIREMENT_SKILL] == ["Flux"]

        neither = _resume(skills=[
            _skill("React", "Frontend and Web Development", "used", "Built views in React.", "projects"),
        ])
        missing = _match(compare(neither, job), skill_name="Flux")
        assert missing.outcome == OUTCOME_MISSING
        assert missing.evidence == [] and "React" not in missing.related_skills
        assert "Flux" in missing.requirement.text and "Redux" in missing.requirement.text

        redux = _resume(skills=[
            _skill("Redux", "Frontend and Web Development", "used", "Stored state with Redux.", "projects"),
        ])
        matched = _match(compare(redux, job), skill_name="Flux")
        assert matched.outcome == OUTCOME_MATCHED
        assert matched.satisfied_by == "Redux"
        assert matched.evidence and "Redux" in matched.evidence[0].text
        shown = [row for _outcome, _heading, rows in comparison_groups(compare(redux, job)) for row in rows]
        assert shown[0].label == "Flux or Redux"
        assert any(line.startswith("Posting:") and "Flux" in line and "Redux" in line for line in shown[0].display_lines())

        flux = _resume(projects=[
            ProjectEntry(name="Store", raw_text="Implemented the store with Flux.",
                         description=["Implemented the store with Flux."]),
        ])
        flux_match = _match(compare(flux, job), skill_name="Flux")
        assert flux_match.outcome == OUTCOME_MATCHED
        assert flux_match.satisfied_by == "Flux"
        assert "Flux" in flux_match.evidence[0].text

    def test_and_list_is_not_an_alternative_group(self):
        job = analyze_job("Requirements\n- Python and SQL\n")
        assert _requirement(job, skill_name="Python").alternatives == []
        assert _requirement(job, skill_name="SQL").alternatives == []

    def test_project_mentions_do_not_prove_years_with_a_skill(self):
        job = analyze_job(
            "Requirements\n"
            "- 3+ years of professional experience\n"
            "- 2+ years with React\n"
        )
        unrelated = _resume(
            experience=[ExperienceEntry(
                title="Java Developer", organization="Demo Ltd", start_date="Jan 2018",
                end_date="Jan 2024", raw_text="Java Developer, Demo Ltd (Jan 2018 - Jan 2024)",
            )],
            projects=[ProjectEntry(name="Puzzle", raw_text="Puzzle built with React", technologies=["React"])],
        )
        report = compare(unrelated, job, as_of=AS_OF)
        general = _match(report, kind=REQUIREMENT_EXPERIENCE, experience_focus=None)
        react_years = _match(report, kind=REQUIREMENT_EXPERIENCE, experience_focus="React")
        assert general.outcome == OUTCOME_MATCHED and general.support
        assert "Demo Ltd" in general.support[0]
        assert react_years.outcome == OUTCOME_INDETERMINATE
        assert "unverif" in (react_years.note or "").lower()
        assert "React" in react_years.requirement.text
        assert not any("Puzzle" in line for line in react_years.support)

        employed = _resume(experience=[ExperienceEntry(
            title="Frontend Developer", organization="Demo Ltd", start_date="Jan 2022",
            end_date="Jan 2026", description=["Built interfaces with React."],
            raw_text="Frontend Developer, Demo Ltd (Jan 2022 - Jan 2026)\n- Built interfaces with React.",
        )])
        proved = compare(employed, job, as_of=AS_OF)
        proved_react = _match(proved, kind=REQUIREMENT_EXPERIENCE, experience_focus="React")
        assert proved_react.outcome == OUTCOME_MATCHED
        assert proved_react.support and "React" in proved_react.support[0]

    def test_combined_duration_is_not_a_react_skill(self):
        job = analyze_job(
            "Requirements\n"
            "- 3 years of professional web development experience, including 2 years with React.\n"
            "- React\n"
        )
        skills = [item for item in job.requirements if item.kind == REQUIREMENT_SKILL]
        assert [item.skill_name for item in skills] == ["React"]
        assert "year" not in skills[0].text.lower()
        general = _requirement(job, kind=REQUIREMENT_EXPERIENCE, years_min=3)
        focused = _requirement(job, kind=REQUIREMENT_EXPERIENCE, years_min=2, experience_focus="React")
        assert general.experience_focus is None
        assert "React" in focused.text

        resume = analyze_text(
            "ALEX EXAMPLE\nalex.example@example.com\n\n"
            "TECHNICAL SKILLS\nReact.js, JavaScript\n\n"
            "PROJECTS\nPuzzle | React.js\n- Interactive puzzle built with React.\n",
            "text",
        )
        report = compare(resume, job, as_of=AS_OF)
        assert _match(report, skill_name="React").outcome == OUTCOME_MATCHED
        years = _match(report, kind=REQUIREMENT_EXPERIENCE, experience_focus="React")
        assert years.outcome == OUTCOME_INDETERMINATE
        assert years.outcome not in (OUTCOME_MATCHED, OUTCOME_MISSING)
        assert "unverif" in (years.note or "").lower()
        assert "satisfied or failed" in (years.note or "").lower()
        assert not any("Puzzle" in line or "React" in line for line in years.support)
        general_match = _match(report, kind=REQUIREMENT_EXPERIENCE, experience_focus=None)
        assert general_match.outcome == OUTCOME_INDETERMINATE

    def test_slash_and_comma_or_are_one_alternative(self):
        slash = analyze_job("Requirements\n- Redux/Flux\n")
        slash_item = _requirement(slash, kind=REQUIREMENT_SKILL)
        assert set(slash_item.alternatives) == {"Redux", "Flux"}
        assert len([item for item in slash.requirements if item.kind == REQUIREMENT_SKILL]) == 1

        listed = analyze_job("Requirements\n- Redux, Flux, or state management\n")
        listed_item = _requirement(listed, kind=REQUIREMENT_SKILL)
        assert listed_item.alternatives == ["Redux", "Flux", "state management"]

        mixed = analyze_job("Requirements\n- React, Redux or Flux, and JavaScript\n")
        assert _requirement(mixed, skill_name="React").alternatives == []
        assert _requirement(mixed, skill_name="JavaScript").alternatives == []
        assert set(_requirement(mixed, skill_name="Redux").alternatives) == {"Redux", "Flux"}

    def test_duplicate_redux_flux_requirements_collapse(self):
        job = analyze_job(
            "Requirements\n"
            "- Redux\n"
            "- Flux\n"
            "- Redux or Flux\n"
            "- state management\n"
        )
        skills = [item for item in job.requirements if item.kind == REQUIREMENT_SKILL]
        assert len(skills) == 1
        assert set(skills[0].alternatives) == {"Redux", "Flux", "state management"}

        separate = analyze_job("Requirements\n- Redux\n- Flux\n")
        assert [item.skill_name for item in separate.requirements if item.kind == REQUIREMENT_SKILL] == ["Redux", "Flux"]
        assert all(item.alternatives == [] for item in separate.requirements)

        hooks = analyze_job("Requirements\n- React\n- React hooks\n")
        assert [item.skill_name for item in hooks.requirements] == ["React", "React hooks"]


class TestSuppliedProse:
    def test_about_the_job_prose_uses_only_named_taxonomy_skills(self):
        job = analyze_job(
            "About the job\n"
            "Description\n\n"
            "As a Front-End Developer, you will have the opportunity to create dynamic, "
            "responsive websites using JavaScript, HTML5, and CSS3. You will also work "
            "with popular no-code tools like Webflow to deliver high-quality solutions "
            "for global clients.\n"
        )
        skills = [item for item in job.requirements if item.kind == REQUIREMENT_SKILL]
        assert {item.skill_name for item in skills} == {"JavaScript", "HTML", "CSS", "Webflow"}
        assert all(item.priority == PRIORITY_UNSPECIFIED for item in skills)
        assert "HTML5" in _requirement(job, skill_name="HTML").text
        assert "CSS3" in _requirement(job, skill_name="CSS").text
        assert "React" not in {item.skill_name for item in skills}

    def test_tools_outside_the_taxonomy_are_not_invented(self):
        job = analyze_job(
            "Required qualifications\n"
            "- Experience with Zig\n"
            "- Must have COBOL\n"
            "Preferred\n"
            "- Elixir is a plus\n"
        )
        assert job.status == STATUS_PARTIAL
        assert job.requirements == []
        assert job.reason == "No requirements could be identified."

    def test_symbol_only_and_very_short_text_stay_empty(self):
        symbols = analyze_job("@@@ ### $$$ %%%")
        assert symbols.status == STATUS_EMPTY
        assert symbols.requirements == []
        short = analyze_job("Python")
        assert short.status == STATUS_EMPTY
