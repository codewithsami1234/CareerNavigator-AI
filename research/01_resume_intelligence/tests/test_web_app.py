"""Web-layer tests. The Streamlit script is exercised with AppTest, not a browser."""
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config
import sample_data as sd
from pipeline import analyze_job, analyze_text, career_report
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, PRIORITY_PREFERRED,
    STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_SUCCESS, ContactInfo, ResumeAnalysis,
)
from web import service
from github_analysis.analyze import GitHubAnalysis, GitHubRepository, GitHubSkillEvidence
from web.view_model import (
    FRESHER_EXPERIENCE_MESSAGE, contact_fields, display_warnings, experience_entries,
    experience_tab_notice, extracted_preview, github_profile_lines, github_repository_lines,
    missing_contact_labels, readiness_lines, recommendation_lines, roadmap_lines, status_notice,
)

APP = Path(__file__).resolve().parents[1] / "web" / "app.py"


def _visible(at) -> str:
    chunks = []
    for group in (
        at.title, at.header, at.subheader, at.markdown, at.caption, at.text,
        at.warning, at.error, at.info, at.success, at.metric,
    ):
        for element in group:
            chunks.append(str(getattr(element, "value", "") or ""))
            chunks.append(str(getattr(element, "label", "") or ""))
    return "\n".join(chunks)


def _click(at, label):
    matches = [button for button in at.button if button.label == label]
    assert matches, [button.label for button in at.button]
    return matches[0].click().run()


def _start():
    at = AppTest.from_file(str(APP), default_timeout=60)
    at.run()
    assert not at.exception
    return at


class TestUploadService:
    def test_text_resume_reaches_phase1(self):
        analysis = service.analyze_upload("alex.txt", sd.FULL_RESUME.encode("utf-8"))
        assert analysis.status == STATUS_SUCCESS
        assert analysis.file_name == "alex.txt"
        assert analysis.contact.email == "alex.morgan@example.com"
        assert any(skill.name == "Python" for skill in analysis.skills)
        assert analysis.education and analysis.experience

    def test_path_in_the_filename_cannot_escape(self, tmp_path):
        seen = {}

        def resume(path, taxonomy_path=None):
            seen["path"] = Path(path)
            assert seen["path"].is_file()
            return ResumeAnalysis(status=STATUS_EMPTY, file_name=seen["path"].name)

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(service, "analyze_resume", resume)
        try:
            analysis = service.analyze_upload(r"..\private\alex.txt", b"hello resume text\n" * 5)
        finally:
            monkeypatch.undo()
        assert analysis.file_name == "alex.txt"
        assert not seen["path"].exists()
        assert not seen["path"].parent.exists()

    def test_pdf_ocr_flag_selects_phase2(self, monkeypatch):
        calls = []

        def resume(path, taxonomy_path=None):
            calls.append("resume")
            return ResumeAnalysis(status=STATUS_NEEDS_OCR, file_name=Path(path).name)

        def document(path, taxonomy_path=None, *, ocr=True, tesseract_cmd=None, ocr_lang=None):
            calls.append(("document", ocr))
            return ResumeAnalysis(status=STATUS_SUCCESS, file_name=Path(path).name)

        monkeypatch.setattr(service, "analyze_resume", resume)
        monkeypatch.setattr(service, "analyze_document", document)
        off = service.analyze_upload("scan.pdf", b"%PDF-1.4\n", use_ocr=False)
        on = service.analyze_upload("scan.pdf", b"%PDF-1.4\n", use_ocr=True)
        text = service.analyze_upload("notes.txt", b"a resume with enough letters\n", use_ocr=True)
        assert off.status == STATUS_NEEDS_OCR
        assert on.status == STATUS_SUCCESS
        assert text.file_name == "notes.txt"
        assert calls == ["resume", ("document", True), "resume"]

    def test_image_uses_phase2_and_a_bad_signature_is_not_written(self, monkeypatch):
        calls = []

        def document(path, taxonomy_path=None, *, ocr=True, tesseract_cmd=None, ocr_lang=None):
            calls.append(ocr)
            return ResumeAnalysis(
                status=STATUS_SUCCESS if ocr else STATUS_NEEDS_OCR,
                file_name=Path(path).name,
                source_format="image",
            )

        monkeypatch.setattr(service, "analyze_document", document)
        png = b"\x89PNG\r\n\x1a\nrest"
        off = service.analyze_upload("photo.png", png, use_ocr=False)
        on = service.analyze_upload("photo.jpg", b"\xff\xd8\xffrest", use_ocr=True)
        assert off.status == STATUS_NEEDS_OCR
        assert on.status == STATUS_SUCCESS
        assert calls == [False, True]
        level, message = status_notice(off)
        assert level == "warning" and "photograph" in message.lower()

        created = []
        monkeypatch.setattr(service.tempfile, "mkdtemp", lambda *args, **kwargs: created.append("called") or (_ for _ in ()).throw(AssertionError("temp")))
        rejected = service.analyze_upload("notes.txt", b"MZ" + b"\x00" * 20)
        assert rejected.status == STATUS_FAILED
        assert created == []
        assert "plain text" in rejected.errors[0].lower() or "binary" in rejected.errors[0].lower()

    def test_invalid_empty_and_oversized_uploads(self, monkeypatch):
        assert config.MAX_FILE_SIZE_MB == 10
        unsupported = service.analyze_upload("resume.rtf", b"{\\rtf1 hi}")
        assert unsupported.status == STATUS_FAILED
        assert "unsupported" in unsupported.errors[0].lower()

        empty = service.analyze_upload("empty.txt", b"")
        assert empty.status == STATUS_FAILED and "empty" in empty.errors[0].lower()

        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 32)
        oversized = service.analyze_upload("big.txt", b"x" * 200)
        assert oversized.status == STATUS_FAILED
        assert "too large" in oversized.errors[0].lower()
        assert config.MAX_FILE_SIZE_MB == 10

    def test_malformed_and_encrypted_files_do_not_raise(self, tmp_path):
        broken = service.analyze_upload("broken.pdf", b"%PDF-1.4 this is not a document")
        assert broken.status == STATUS_FAILED and broken.errors
        encrypted = sd.write_encrypted_pdf(tmp_path / "secret.pdf").read_bytes()
        locked = service.analyze_upload("secret.pdf", encrypted)
        assert locked.status == STATUS_FAILED and locked.errors
        assert locked.skills == []

    def test_sparse_text_is_empty(self):
        analysis = service.analyze_upload("tiny.txt", b" \n\n\t\n")
        assert analysis.status == STATUS_EMPTY
        assert analysis.skills == []


class TestViewModel:
    def test_missing_contact_is_not_invented(self):
        analysis = ResumeAnalysis(status=STATUS_SUCCESS, contact=ContactInfo(email="a@example.com"))
        assert contact_fields(analysis) == [("Email", "a@example.com")]
        assert "Name" in missing_contact_labels(analysis)
        assert extracted_preview(analysis) == ""

    def test_notices_match_pipeline_statuses(self):
        assert status_notice(ResumeAnalysis(status=STATUS_FAILED, errors=["bad file"]))[0] == "error"
        assert status_notice(ResumeAnalysis(status=STATUS_EMPTY))[0] == "warning"
        level, message = status_notice(ResumeAnalysis(status=STATUS_NEEDS_OCR))
        assert level == "warning" and "OCR" in message
        assert "not verified" in status_notice(ResumeAnalysis(status=STATUS_SUCCESS))[1]


class TestStreamlitWorkflow:
    def test_page_explains_the_local_reader(self):
        text = _visible(_start())
        assert "CareerNavigator AI" in text
        assert "rule-based estimate" in text
        assert "not an ATS score" in text
        assert "resume is not sent" in text

    def test_analyze_without_a_file_is_an_error(self):
        at = _click(_start(), "Analyze resume")
        assert not at.exception
        assert "Choose a PDF, DOCX, TXT, PNG, or JPEG resume first." in _visible(at)

    def test_valid_text_upload_shows_pipeline_fields(self):
        at = _start()
        at.file_uploader[0].upload("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        assert not at.exception
        text = _visible(at)
        assert "alex.morgan@example.com" in text
        assert "Python" in text
        assert "not verified facts" in text
        assert any(element.label == "Skills" and int(element.value) > 0 for element in at.metric)

    def test_uploader_allows_only_pipeline_document_types(self):
        at = _start()
        assert sorted(at.file_uploader[0].allowed_type) == [".docx", ".jpeg", ".jpg", ".pdf", ".png", ".txt"]

    def test_empty_malformed_and_oversized_uploads(self, monkeypatch):
        at = _start()
        at.file_uploader[0].upload("blank.txt", b" \n\n", "text/plain")
        at = _click(at, "Analyze resume")
        assert "enough meaningful text" in _visible(at)

        at = _start()
        at.file_uploader[0].upload("broken.pdf", b"%PDF-1.4 garbage", "application/pdf")
        at = _click(at, "Analyze resume")
        assert not at.exception
        assert at.session_state["analysis"].status == STATUS_FAILED

        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 16)
        at = _start()
        at.file_uploader[0].upload("big.txt", b"x" * 80, "text/plain")
        at = _click(at, "Analyze resume")
        assert "too large" in _visible(at).lower()
        assert config.MAX_FILE_SIZE_MB == 10

    def test_scanned_pdf_warns_that_ocr_was_not_run(self, tmp_path):
        data = sd.write_image_only_pdf(tmp_path / "scan.pdf").read_bytes()
        at = _start()
        at.file_uploader[0].upload("scan.pdf", data, "application/pdf")
        at = _click(at, "Analyze resume")
        assert not at.exception
        text = _visible(at)
        assert "OCR was not run" in text
        assert "Python" not in text

FRESHER_RESUME = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
Python, Git, SQL

PROJECTS
Library System | Python
- Built a console library for a university course using Python.
"""

UNPARSED_EXPERIENCE_RESUME = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
Python, Git, SQL

EXPERIENCE

PROJECTS
Library System | Python
- Built a console library for a university course using Python.
"""

FRESHER_JOB = """
Requirements
- Python
- 2+ years of professional experience

Preferred
- Docker
"""


class TestFresherExperience:
    def test_missing_experience_section_is_successful_and_neutral(self):
        analysis = analyze_text(FRESHER_RESUME, "text")
        assert analysis.status == STATUS_SUCCESS
        assert analysis.errors == []
        assert analysis.experience == []
        assert analysis.projects
        assert any(skill.name == "Python" for skill in analysis.skills)
        assert "Section not detected: experience." in analysis.warnings
        assert "Section not detected: education." in analysis.warnings
        shown = display_warnings(analysis)
        assert ("info", FRESHER_EXPERIENCE_MESSAGE) in shown
        assert ("warning", "Section not detected: education.") in shown
        assert experience_tab_notice(analysis) == FRESHER_EXPERIENCE_MESSAGE
        assert experience_entries(analysis) == []

    def test_other_missing_sections_stay_warnings(self):
        analysis = analyze_text(FRESHER_RESUME, "text")
        education = [
            message for level, message in display_warnings(analysis)
            if message == "Section not detected: education."
        ]
        assert education == ["Section not detected: education."]
        assert all(
            level == "warning" for level, message in display_warnings(analysis)
            if message == "Section not detected: education."
        )

    def test_unparsed_experience_heading_stays_a_limitation(self):
        analysis = analyze_text(UNPARSED_EXPERIENCE_RESUME, "text")
        assert analysis.status == STATUS_SUCCESS
        assert analysis.experience == []
        assert analysis.projects
        limitation = "An Experience section was found but no job entries could be identified."
        assert limitation in analysis.warnings
        assert "Section not detected: experience." not in analysis.warnings
        shown = display_warnings(analysis)
        assert ("warning", limitation) in shown
        assert all(message != FRESHER_EXPERIENCE_MESSAGE for _level, message in shown)
        assert experience_tab_notice(analysis) == limitation

    def test_project_evidence_does_not_satisfy_professional_years(self):
        analysis = analyze_text(FRESHER_RESUME, "text")
        job = analyze_job(FRESHER_JOB)
        report = career_report(analysis, job, as_of=date(2026, 10, 18))
        comparison = report.comparison
        python = next(item for item in comparison.matches if item.requirement.skill_name == "Python")
        docker = next(item for item in comparison.matches if item.requirement.skill_name == "Docker")
        experience = next(item for item in comparison.matches if item.requirement.kind == "experience")
        assert python.outcome == OUTCOME_MATCHED and python.evidence
        assert docker.outcome == OUTCOME_MISSING
        assert docker.requirement.priority == PRIORITY_PREFERRED
        assert docker.evidence == []
        assert "lack" not in (docker.note or "").lower()
        assert experience.outcome == OUTCOME_INDETERMINATE
        assert "project" in (experience.note or "").lower()
        assert not any(project.name and project.name in " ".join(experience.support) for project in analysis.projects)
        assert report.readiness.estimate == 100
        assert "not a validated prediction" in report.readiness.disclaimer.lower()
        assert "not an ats score" in report.readiness.disclaimer.lower()
        assert "Python" in report.recommendations.matched_skills
        assert any(item.skill_name == "Docker" and item.gap_kind == "missing_preferred" for item in report.recommendations.items)
        assert report.recommendations.experience_gaps

    def test_page_shows_the_fresher_notice_and_keeps_the_finding(self):
        at = _start()
        at.file_uploader[0].upload("fresher.txt", FRESHER_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        assert not at.exception
        text = _visible(at)
        assert FRESHER_EXPERIENCE_MESSAGE in text
        assert "Section not detected: experience." not in text
        assert "Section not detected: education." in text
        assert "Python" in text
        analysis = at.session_state["analysis"]
        assert analysis.status == STATUS_SUCCESS
        assert analysis.experience == []
        assert "Section not detected: experience." in analysis.warnings


class TestCareerFeatures:
    def test_profile_counts_distinguish_missing_from_zero(self):
        missing = GitHubAnalysis(status="success", username="octocat", public_repos=None, repositories=[])
        zero = GitHubAnalysis(status="success", username="octocat", public_repos=0, repositories=[])
        assert "not provided" in "\n".join(github_profile_lines(missing))
        assert "Public repositories reported by GitHub: 0" in github_profile_lines(zero)
        blank = GitHubRepository(name="demo", url="https://github.com/octocat/demo")
        blank_lines = github_repository_lines(blank)
        assert "No description was provided." in blank_lines
        assert "Languages: none listed" in blank_lines
        assert "Last push time: not provided" in blank_lines
        unavailable = GitHubRepository(
            name="demo", url="https://github.com/octocat/demo",
            warnings=["Languages were not accessible for this repository."],
        )
        assert "Languages: not available" in github_repository_lines(unavailable)

    def test_displayed_estimate_matches_the_assessment(self):
        analysis = analyze_text(FRESHER_RESUME, "text")
        report = career_report(analysis, analyze_job(FRESHER_JOB), as_of=date(2026, 10, 18))
        lines = readiness_lines(report.readiness)
        estimate_line = f"Rule-based estimate: {report.readiness.estimate} out of 100"
        assert any(line.startswith(estimate_line) for line in lines)
        assert report.readiness.estimate == 100
        assert any(line.startswith("Python · required · supported · scored · credit 1") for line in lines)
        assert any("not scored" in line and "experience" in line.lower() for line in lines)
        assert any(item.gap_kind == "missing_preferred" for item in report.recommendations.items)
        recommended = "\n".join(recommendation_lines(report.recommendations))
        assert "Docker · Missing preferred skill" in recommended
        assert "Unverified professional experience" in recommended
        milestones = "\n".join(roadmap_lines(report.roadmap))
        assert "\n1. " in "\n" + milestones
        assert "Done when:" in milestones
        assert milestones.index("Docker") < milestones.index("Employment evidence")

    def test_resume_without_a_job_has_no_numeric_estimate(self):
        at = _start()
        at.file_uploader[0].upload("fresher.txt", FRESHER_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        text = _visible(at)
        assert FRESHER_EXPERIENCE_MESSAGE in text
        assert "No job description was supplied" in text
        assert "No GitHub profile has been requested" in text
        assert "No numeric estimate was calculated." in text
        assert "100 / 100" not in text

    def test_page_shows_comparison_readiness_recommendations_and_roadmap(self):
        at = _start()
        at.file_uploader[0].upload("fresher.txt", FRESHER_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        at.text_area[0].set_value(FRESHER_JOB).run()
        at = _click(at, "Compare with resume")
        text = _visible(at)
        assert "Matched" in text
        assert "Python · required · used" in text or "Python · required · mentioned" in text
        assert "Not enough information" in text
        assert "100 / 100" in text
        assert "Rule-based estimate: 100 out of 100" in text
        assert "Missing preferred skill" in text
        assert "Docker" in text
        assert "Done when:" in text
        assert "not an ATS score" in text
        assert FRESHER_EXPERIENCE_MESSAGE in text
        at.number_input[0].set_value(4).run()
        planned = _visible(at)
        assert "4" in planned
        assert "No measured study duration" in planned or "not a guarantee" in planned

    def test_invalid_github_keeps_the_resume(self):
        at = _start()
        at.file_uploader[0].upload("fresher.txt", FRESHER_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        at = _click(at, "Read public GitHub profile")
        assert "Enter a GitHub username or a public profile URL." in _visible(at)
        assert "No GitHub profile has been requested" in _visible(at)
        at.text_input[0].set_value("https://gitlab.com/octocat").run()
        at = _click(at, "Read public GitHub profile")
        text = _visible(at)
        assert "Python" in text
        assert FRESHER_EXPERIENCE_MESSAGE in text
        assert "github.com" in text.lower()

    def test_mocked_github_stays_separate_from_resume_evidence(self, monkeypatch):
        def fake(value):
            return GitHubAnalysis(
                status="success",
                username="octocat",
                profile_url="https://github.com/octocat",
                public_repos=0,
                repositories=[GitHubRepository(
                    name="demo", url="https://github.com/octocat/demo", description=None,
                    languages=["Python"], pushed_at="2024-01-02T03:04:05Z",
                )],
                skills=[GitHubSkillEvidence(
                    skill_name="Python", repository="demo",
                    repository_url="https://github.com/octocat/demo",
                    source_field="languages", text="Python",
                    note="Present in the repository language list. This is not a proficiency level.",
                )],
                limitations=["Only public GitHub API data is read. Private repositories are skipped."],
            )

        monkeypatch.setattr(service, "read_github_profile", fake)
        at = _start()
        at.file_uploader[0].upload("fresher.txt", FRESHER_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        at.text_input[0].set_value("octocat").run()
        at = _click(at, "Read public GitHub profile")
        text = _visible(at)
        assert "Public repositories reported by GitHub: 0" in text
        assert "not a measure of professional ability" in text
        assert "not resume evidence" in text
        assert "https://github.com/octocat/demo" in text
        assert "Last push recorded by GitHub: 2024-01-02T03:04:05Z" in text
        assert "Python" in text
        assert FRESHER_EXPERIENCE_MESSAGE in text

    def test_unlabeled_webflow_posting_has_no_numeric_estimate(self):
        resume = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
JavaScript, HTML, CSS
"""
        posting = """
Front-End Developer

This role builds marketing pages with JavaScript, HTML5, CSS3, and Webflow.
Designers review the pages in the browser.
"""
        at = _start()
        at.file_uploader[0].upload("frontend.txt", resume.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        at.text_area[0].set_value(posting).run()
        at = _click(at, "Compare with resume")
        text = _visible(at)
        assert "JavaScript · unspecified" in text
        assert "HTML · unspecified" in text
        assert "CSS · unspecified" in text
        assert "Webflow · unspecified" in text
        assert "Missing" in text
        assert "Webflow · Missing skill, priority not stated · unspecified" in text
        assert "1. Webflow · Missing skill, priority not stated" in text
        assert "JavaScript · Missing" not in text
        assert "HTML · Missing" not in text
        assert "CSS · Missing" not in text
        assert "No numeric estimate" in text
        assert "denominator is 0" in text
        assert "100 / 100" not in text
        assert "Rule-based estimate:" not in text


    def test_new_upload_clears_the_result(self):
        at = _start()
        at.file_uploader[0].upload("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")
        at = _click(at, "Analyze resume")
        assert "Python" in _visible(at)
        at = _click(at, "New upload")
        assert not at.exception
        assert at.session_state["analysis"] is None
        assert "Python" not in _visible(at)
