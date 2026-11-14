"""End-to-end tests: sections, entities, status handling, JSON, CLI, evaluation."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

import sample_data as sd
from extractors.section_extractor import SectionExtractor
from pipeline import analyze_resume, analyze_text, extract_skills
from schemas import (STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_PARTIAL, STATUS_SUCCESS)

PROJECT_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def full():
    return analyze_text(sd.FULL_RESUME, "text")


# ------------------------------------------------------------ full resume content
class TestFullResume:
    def test_status_and_format(self, full):
        assert full.status == STATUS_SUCCESS and full.source_format == "text" and not full.errors

    def test_contact(self, full):
        c = full.contact
        assert c.name == "Alex Morgan"
        assert c.email == "alex.morgan@example.com"
        assert c.phone == "+92 300 0000000"
        assert c.location == "Lahore, Pakistan"
        assert c.github == "github.com/alexmorgan-demo" and c.linkedin == "linkedin.com/in/alexmorgan-demo"

    def test_sections_detected_in_order(self, full):
        assert [s.name for s in full.sections] == [
            "header", "summary", "skills", "education", "experience", "projects",
            "certifications", "courses", "achievements", "languages"]

    def test_section_content_is_preserved(self, full):
        exp = next(s for s in full.sections if s.name == "experience")
        assert "Docker" in exp.content and exp.heading == "Experience"

    def test_education(self, full):
        first, second = full.education
        assert (first.degree, first.field_of_study) == ("Bachelor of Science", "Information Technology")
        assert first.institution == "Example University of Technology"
        assert (first.start_year, first.end_year, first.graduation_year) == (2021, 2025, 2025)
        assert first.gpa == "3.4/4.0"
        assert second.degree == "Intermediate in Pre-Engineering"
        assert second.institution == "Sample Government College"
        assert (second.start_year, second.end_year) == (2019, 2021)

    def test_experience(self, full):
        a, b = full.experience
        assert (a.title, a.organization) == ("Software Engineering Intern", "Acme Software Solutions")
        assert (a.start_date, a.end_date, a.is_current) == ("Jun 2024", "Aug 2024", False)
        assert len(a.description) == 2 and a.description[0].startswith("Built REST API")
        assert (b.title, b.organization) == ("Junior Web Developer", "Demo Technologies Ltd")
        assert (b.start_date, b.end_date, b.is_current) == ("Jan 2023", "Present", True)

    def test_projects_and_their_technologies(self, full):
        p1, p2 = full.projects
        assert p1.name == "Smart Attendance System"
        assert {"Python", "OpenCV", "Flask", "SQLite"} <= set(p1.technologies)
        assert p2.name == "Resume Screening Assistant"
        assert set(p2.technologies) == {"scikit-learn", "NLTK"}

    def test_certifications_and_courses(self, full):
        by_name = {c.name: c for c in full.certifications}
        g = by_name["Google Data Analytics Professional Certificate"]
        assert (g.issuer, g.year, g.kind) == ("Coursera", 2023, "certification")
        assert by_name["AWS Cloud Practitioner Essentials"].issuer == "Amazon Web Services"
        ml = by_name["Machine Learning Specialization"]
        assert (ml.kind, ml.issuer) == ("course", "Stanford Online")

    def test_skills_with_evidence(self, full):
        skills = {s.name: s for s in full.skills}
        assert skills["Django"].evidence_type == "used"
        assert skills["SQL"].evidence_type == "mentioned"          # only listed under Skills
        assert skills["scikit-learn"].category == "AI and Machine Learning"
        assert {e.section for e in skills["Python"].evidence} >= {"skills"}
        assert "JavaScript" in skills and "Java" in skills and "Java" != "JavaScript"

    def test_human_languages_not_scanned_as_skills(self, full):
        assert all(e.section != "languages" for s in full.skills for e in s.evidence)


# ------------------------------------------------------------- heading variations
HEADINGS = [
    ("SKILLS", "skills"), ("Technical Skills", "skills"), ("Technical Skills:", "skills"),
    ("Core Competencies", "skills"), ("S K I L L S", "skills"), ("## Skills", "skills"),
    ("--- Skills ---", "skills"), ("  skills  ", "skills"),
    ("EDUCATION", "education"), ("Academic Background", "education"),
    ("Education & Qualifications", "education"),
    ("Work Experience", "experience"), ("PROFESSIONAL EXPERIENCE", "experience"),
    ("Employment History", "experience"), ("Work History", "experience"),
    ("Personal Projects", "projects"), ("Academic Projects", "projects"), ("Final Year Project", "projects"),
    ("Professional Summary", "summary"), ("Objective", "summary"), ("Career Objective", "summary"),
    ("Certifications", "certifications"), ("Licenses & Certifications", "certifications"),
    ("Courses", "courses"), ("Training", "courses"), ("Courses and Training", "courses"),
    ("Achievements", "achievements"), ("Awards", "achievements"),
    ("Languages", "languages"), ("Contact Information", "contact"), ("1. Education", "education"),
    ("Decl a r a tion", "declaration"), ("C a r e e r Objective", "summary"),
    ("S K I L L S and Tools", "skills"), ("Course and Certificates", "courses"),
    ("Academic Interest", "interests"),
]


class TestHeadingVariations:
    @pytest.mark.parametrize("heading,expected", HEADINGS)
    def test_variants(self, heading, expected):
        text = f"Jane Roe\n\n{heading}\nsome content line here\n"
        names = [s.name for s in SectionExtractor().extract(text)]
        assert expected in names, f"{heading!r} -> {names}"

    def test_inline_skills_heading(self):
        secs = SectionExtractor().extract("Jane Roe\nSkills: Python, SQL, Git\nEducation\nBS CS")
        skills = next(s for s in secs if s.name == "skills")
        assert skills.content == "Python, SQL, Git"

    def test_body_text_is_not_a_heading(self):
        text = "Jane Roe\nExperience\n- Gained experience in Python projects and education tools\nSkills in Python"
        names = [s.name for s in SectionExtractor().extract(text)]
        assert names == ["header", "experience"]

    def test_bulleted_heading_word_is_not_a_heading(self):
        names = [s.name for s in SectionExtractor().extract("Jane Roe\n- Skills\nSkills\nPython")]
        assert names.count("skills") == 1

    def test_custom_alias_file(self):
        ex = SectionExtractor(aliases={"skills": ["my stuff"], "education": ["school days"]})
        names = [s.name for s in ex.extract("Name Here\nMY STUFF\nPython\nSchool Days\nBS")]
        assert names == ["header", "skills", "education"]

    def test_different_section_orders(self):
        a = analyze_text(sd.SECTION_ORDER_REVERSED_RESUME)
        assert [s.name for s in a.sections] == ["header", "certifications", "projects", "experience",
                                                "education", "skills"]
        assert a.education[0].degree == "BS" and a.education[0].field_of_study == "Software Engineering"
        assert a.experience[0].title == "Support Engineer"
        assert a.projects[0].name == "Budget Tracker" and "Flask" in a.projects[0].technologies
        assert a.certifications[0].name == "Azure Fundamentals"

    def test_variant_headings_resume(self):
        a = analyze_text(sd.VARIANT_HEADINGS_RESUME)
        assert a.status == STATUS_SUCCESS
        assert [s.name for s in a.sections] == ["header", "skills", "experience", "education",
                                                "projects", "certifications"]
        assert a.experience[0].title == "Backend Developer"
        assert a.experience[0].organization == "Sample Systems Pvt Ltd"
        assert {s.name for s in a.skills} >= {"Python", "Node.js", "MongoDB", "Kubernetes", "WebSockets"}

    def test_skills_sublabels_stay_inside_skills_section(self):
        """Regression: 'Languages: JavaScript...' inside Skills must not start a human-languages section."""
        text = "Jane Roe\nTechnical Skills\nLanguages: JavaScript, TypeScript\nFrameworks: React"
        names = {s.name for s in extract_skills(text)}
        assert names == {"JavaScript", "TypeScript", "React"}


# ---------------------------------------------------------------- missing parts
class TestMissingData:
    def test_missing_contact_details_are_null(self):
        a = analyze_text(sd.NO_CONTACT_RESUME)
        assert a.status == STATUS_SUCCESS
        c = a.contact
        assert (c.name, c.email, c.phone, c.location, c.linkedin, c.github) == (None,) * 6
        assert "No email address found." in a.warnings and "No phone number found." in a.warnings

    def test_missing_sections_give_empty_lists_and_warnings(self):
        a = analyze_text("Jane Roe\njane@example.com\n\nSkills\nPython, SQL, Git, Docker and many more tools\n")
        assert a.education == [] and a.experience == [] and a.projects == [] and a.certifications == []
        assert "Section not detected: education." in a.warnings
        assert "Section not detected: experience." in a.warnings

    def test_no_section_headings_is_partial(self):
        a = analyze_text(sd.NO_SECTIONS_RESUME)
        assert a.status == STATUS_PARTIAL
        assert a.contact.email == "sam.carter@example.com"
        assert {"Python", "Docker", "PostgreSQL", "React"} <= {s.name for s in a.skills}
        assert any("No section headings" in w for w in a.warnings)

    def test_unknown_values_are_not_invented(self):
        a = analyze_text("Skills\nPython, Django, Docker and Flask for building web services\n\n"
                         "Education\nExample University\n")
        e = a.education[0]
        assert e.institution == "Example University"
        assert (e.degree, e.field_of_study, e.start_year, e.end_year, e.graduation_year, e.gpa) == (None,) * 6

    def test_years_and_date_ranges_are_not_phone_numbers(self):
        a = analyze_text("Jane Roe\nBS CS 2019 - 2023 | 2019-2023\n\nSkills\nPython and SQL and Git and Docker and Linux\n")
        assert a.contact.phone is None

    def test_job_title_line_is_not_a_name(self):
        a = analyze_text("Software Engineer\nSkills\nPython and SQL and Git and Docker and Linux and more\n")
        assert a.contact.name is None

    def test_us_state_abbreviation_is_not_a_degree(self):
        a = analyze_text("Skills\nPython, SQL, Git, Docker, Linux, Flask\n\nEducation\nExample University, Boston, MA\n")
        assert a.education[0].degree is None and a.education[0].institution == "Example University"

    def test_experience_without_dates_uses_blocks(self):
        a = analyze_text("Skills\nPython, SQL, Git, Docker, Linux, Flask\n\nExperience\n"
                         "Developer, Acme Corp\n- Built tools\n\nTester, Demo Ltd\n- Wrote tests\n")
        assert [(e.title, e.organization) for e in a.experience] == [("Developer", "Acme Corp"), ("Tester", "Demo Ltd")]
        assert all(e.start_date is None for e in a.experience)

    def test_expected_graduation_is_ongoing(self):
        a = analyze_text("Skills\nPython, SQL, Git, Docker, Linux, Flask\n\nEducation\n"
                         "BS Computer Science, Example University (2021 - Expected 2025)\n")
        e = a.education[0]
        assert e.end_year == 2025 and e.ongoing is True and e.graduation_year is None

    def test_present_end_date_is_ongoing(self):
        a = analyze_text("Skills\nPython, SQL, Git, Docker, Linux, Flask\n\nEducation\n"
                         "MS Data Science, Example University (2023 - Present)\n")
        e = a.education[0]
        assert (e.start_year, e.end_year, e.ongoing, e.graduation_year) == (2023, None, True, None)


# ------------------------------------------------------- analyze_text interface
class TestAnalyzeText:
    def test_empty_text(self):
        a = analyze_text("")
        assert a.status == STATUS_EMPTY and a.warnings

    def test_whitespace_only_text(self):
        assert analyze_text("  \n\n \t ").status == STATUS_EMPTY

    def test_too_little_text(self):
        assert analyze_text("hello").status == STATUS_EMPTY

    def test_non_string_input(self):
        a = analyze_text(None)                       # type: ignore[arg-type]
        assert a.status == STATUS_FAILED and a.errors

    def test_source_format_is_passed_through(self):
        assert analyze_text(sd.FULL_RESUME, "ocr").source_format == "ocr"

    def test_crlf_and_unicode_bullets(self):
        text = sd.FULL_RESUME.replace("\n- ", "\n\u2022 ").replace("\n", "\r\n")
        a = analyze_text(text)
        assert a.status == STATUS_SUCCESS and len(a.experience) == 2


# --------------------------------------------------------- JSON serialisation
class TestJson:
    def test_round_trip_and_keys(self, full):
        data = json.loads(full.to_json())
        assert {"status", "source_format", "contact", "sections", "skills", "education", "experience",
                "projects", "certifications", "warnings", "errors"} <= set(data)
        assert data["contact"]["email"] == "alex.morgan@example.com"
        assert data["skills"][0]["evidence"][0]["section"]

    def test_unknown_values_serialise_as_null(self):
        data = json.loads(analyze_text(sd.NO_CONTACT_RESUME).to_json())
        assert data["contact"]["email"] is None and data["contact"]["name"] is None

    def test_non_ascii_survives(self):
        text = "Jos\u00e9 Garc\u00eda\nSkills\nPython, SQL, Git, Docker, Linux, Flask, React, Java\n"
        data = json.loads(analyze_text(text).to_json())
        assert data["contact"]["name"] == "Jos\u00e9 Garc\u00eda"

    def test_failed_analysis_serialises(self):
        assert json.loads(analyze_resume("missing.pdf").to_json())["status"] == "failed"


# ------------------------------------------------------ file-based entry point
class TestAnalyzeResume:
    def test_same_result_for_txt_docx_pdf(self, tmp_path):
        results = {
            "text": analyze_resume(sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME)),
            "docx": analyze_resume(sd.write_docx(tmp_path / "r.docx", sd.FULL_RESUME)),
            "pdf": analyze_resume(sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME)),
        }
        base = results["text"]
        for fmt, a in results.items():
            assert a.status == STATUS_SUCCESS and a.source_format == fmt, fmt
            assert {s.name for s in a.skills} == {s.name for s in base.skills}, fmt
            assert [s.name for s in a.sections] == [s.name for s in base.sections], fmt
            assert a.contact == base.contact, fmt
            assert [(e.degree, e.institution, e.end_year) for e in a.education] == \
                   [(e.degree, e.institution, e.end_year) for e in base.education], fmt
            assert [(e.title, e.organization) for e in a.experience] == \
                   [(e.title, e.organization) for e in base.experience], fmt
        assert results["pdf"].page_count == 1

    def test_docx_with_table(self, tmp_path):
        a = analyze_resume(sd.write_docx_with_table(tmp_path / "t.docx"))
        assert a.status == STATUS_SUCCESS
        assert {"Python", "Java", "Git", "Docker"} <= {s.name for s in a.skills}
        assert a.education[0].degree == "BS" and a.education[0].end_year == 2023

    def test_image_only_pdf_is_needs_ocr_not_success(self, tmp_path):
        a = analyze_resume(sd.write_image_only_pdf(tmp_path / "scan.pdf"))
        assert a.status == STATUS_NEEDS_OCR
        assert a.skills == [] and a.sections == [] and a.text_length == 0
        assert any("OCR" in w for w in a.warnings)

    @pytest.mark.parametrize("name,writer,status", [
        ("enc.pdf", sd.write_encrypted_pdf, STATUS_FAILED),
        ("empty.docx", sd.write_empty_docx, STATUS_EMPTY),
    ])
    def test_error_statuses(self, tmp_path, name, writer, status):
        a = analyze_resume(writer(tmp_path / name))
        assert a.status == status and (a.errors or a.warnings)
        assert a.skills == []

    @pytest.mark.parametrize("bad", ["missing.pdf", "", "notes.doc"])
    def test_bad_paths_never_raise(self, tmp_path, bad):
        a = analyze_resume(tmp_path / bad if bad else bad)
        assert a.status == STATUS_FAILED and a.errors

    def test_none_path_never_raises(self):
        assert analyze_resume(None).status == STATUS_FAILED      # type: ignore[arg-type]

    def test_malformed_files_fail_cleanly(self, tmp_path):
        for ext in ("pdf", "docx"):
            f = tmp_path / f"bad.{ext}"
            f.write_bytes(b"garbage" * 20)
            a = analyze_resume(f)
            assert a.status == STATUS_FAILED and a.errors and a.sections == []

    def test_file_name_but_not_full_path_is_reported(self, tmp_path):
        a = analyze_resume(sd.write_txt(tmp_path / "private_name.txt", sd.FULL_RESUME))
        assert a.file_name == "private_name.txt" and str(tmp_path) not in a.to_json()

    def test_custom_taxonomy_path(self, tmp_path):
        tax = tmp_path / "t.json"
        tax.write_text(json.dumps({"categories": {"X": [{"name": "Django"}]}}))
        a = analyze_resume(sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME), taxonomy_path=tax)
        assert [s.name for s in a.skills] == ["Django"]


# ------------------------------------------------------------------------- CLI
def run_cli(*args):
    return subprocess.run([sys.executable, "main.py", *map(str, args)], cwd=PROJECT_DIR,
                          capture_output=True, text=True, encoding="utf-8")


class TestCli:
    def test_summary_output_and_exit_code(self, tmp_path):
        f = sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME)
        r = run_cli(f)
        assert r.returncode == 0
        assert "Status:  SUCCESS" in r.stdout and "Alex Morgan" in r.stdout and "Django*" in r.stdout

    def test_output_file_is_valid_json(self, tmp_path):
        f = sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME)
        out = tmp_path / "nested" / "result.json"
        r = run_cli(f, "--output", out)
        assert r.returncode == 0 and out.exists()
        assert json.loads(out.read_text(encoding="utf-8"))["source_format"] == "pdf"

    def test_json_flag_prints_json(self, tmp_path):
        f = sd.write_docx(tmp_path / "r.docx", sd.FULL_RESUME)
        r = run_cli(f, "--json")
        assert json.loads(r.stdout)["contact"]["name"] == "Alex Morgan"

    def test_missing_file_returns_nonzero(self, tmp_path):
        r = run_cli(tmp_path / "nope.pdf")
        assert r.returncode == 1 and "ERROR" in r.stdout

    def test_scanned_pdf_reports_ocr_and_nonzero(self, tmp_path):
        r = run_cli(sd.write_image_only_pdf(tmp_path / "scan.pdf"))
        assert r.returncode == 1 and "NEEDS_OCR" in r.stdout and "OCR" in r.stdout
        assert "Phase 1" in r.stdout and "Phase 2" in r.stdout
        assert "will be added" not in r.stdout

    def test_ocr_flag_labels_phase2_when_tesseract_is_missing(self, tmp_path):
        r = run_cli(
            sd.write_image_only_pdf(tmp_path / "scan.pdf"),
            "--ocr",
            "--tesseract",
            r"C:\missing\tesseract.exe",
        )
        assert r.returncode == 1
        assert "Phase 2" in r.stdout and "FAILED" in r.stdout and "Tesseract" in r.stdout
        assert "will be added" not in r.stdout

    def test_bundled_fixtures_run(self):
        for name in ("sample_resume_full.pdf", "sample_resume_full.docx", "sample_resume_full.txt"):
            assert run_cli(FIXTURES / name).returncode == 0, name


# ------------------------------------------------------------------ evaluation
class TestEvaluation:
    def test_evaluation_script_runs_and_reports_counts(self):
        sys.path.insert(0, str(PROJECT_DIR / "evaluation"))
        import evaluate_skills as ev
        examples = json.loads((PROJECT_DIR / "evaluation" / "labelled_examples.json").read_text(encoding="utf-8"))
        rep = ev.evaluate(examples)
        assert rep["examples"] == len(examples) == 50
        assert rep["true_positives"] + rep["false_negatives"] == sum(len(e["expected_skills"]) for e in examples)
        assert 0 <= rep["f1"] <= 1

    def test_prf_helper(self):
        import evaluate_skills as ev
        assert ev.prf(8, 2, 2)[:2] == (0.8, 0.8)
        assert ev.prf(0, 0, 0) == (None, None, None)
