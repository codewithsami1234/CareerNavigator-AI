"""Streamlit view-model and upload tests for job-description comparison."""
import tempfile
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import config
import sample_data as sd
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, OUTCOME_RELATED,
    STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_SUCCESS, DetectedSkill,
    JobRequirement, MatchReport, RequirementMatch, ResumeAnalysis, SkillEvidence,
)
from web import service
from web.view_model import comparison_groups, job_feedback

APP = Path(__file__).resolve().parents[1] / "web" / "app.py"

JOB_TEXT = """Requirements
- Python
- Pygame
- several years of experience

Preferred
- PyTorch
"""


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


def _with_resume():
    at = _start()
    at.file_uploader[0].upload("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")
    at = _click(at, "Analyze resume")
    assert not at.exception
    return at


def _skill_match(name, priority, evidence_type, line, outcome, category="Programming Languages"):
    requirement = JobRequirement(
        kind="skill", priority=priority, text=f"- {name}", skill_name=name, skill_category=category,
    )
    evidence = []
    if line:
        evidence.append(SkillEvidence(section="projects", text=line, evidence_type=evidence_type or "mentioned", matched_as=name))
    return RequirementMatch(
        requirement=requirement,
        outcome=outcome,
        evidence_type=evidence_type,
        evidence=evidence,
        related_skills=["TensorFlow"] if outcome == OUTCOME_RELATED else [],
        note="The posting does not state a number of years." if outcome == OUTCOME_INDETERMINATE else None,
    )


class TestJobService:
    def test_pasted_text_and_empty_input(self):
        job = service.analyze_job_input("Requirements\n- Python is required for this backend role.\n")
        assert job.status == STATUS_SUCCESS
        assert any(item.skill_name == "Python" and item.priority == "required" for item in job.requirements)

        empty = service.analyze_job_input("   \n")
        assert empty.status == STATUS_EMPTY
        assert empty.requirements == []
        assert empty.reason
        assert service.analyze_job_input(filename="empty.txt", data=b"").status == STATUS_FAILED

    def test_malformed_upload_and_cleanup_on_success_and_failure(self, monkeypatch):
        created = []
        real_mkdtemp = tempfile.mkdtemp

        def tracking(*args, **kwargs):
            path = real_mkdtemp(*args, **kwargs)
            created.append(path)
            return path

        monkeypatch.setattr(service.tempfile, "mkdtemp", tracking)

        def refuse_ocr(*_args, **_kwargs):
            raise AssertionError("OCR")

        monkeypatch.setattr(service, "analyze_document", refuse_ocr)
        original_analyze_job = service.analyze_job

        ok = service.analyze_job_input(
            filename="role.txt",
            data=b"Requirements\n- Python is required for backend services.\n",
        )
        assert ok.status == STATUS_SUCCESS
        assert any(item.skill_name == "Python" for item in ok.requirements)
        assert created and all(not Path(path).exists() for path in created)

        def explode(path, taxonomy_path=None):
            assert Path(path).is_file()
            raise RuntimeError("boom")

        monkeypatch.setattr(service, "analyze_job", explode)
        failed = service.analyze_job_input(filename="role.txt", data=b"Requirements\n- Python is required.\n")
        assert failed.status == STATUS_FAILED
        assert "RuntimeError" in failed.errors[0]
        assert all(not Path(path).exists() for path in created)

        monkeypatch.setattr(service, "analyze_job", original_analyze_job)
        broken = service.analyze_job_input(filename="broken.pdf", data=b"This is not really a PDF file.")
        assert broken.status == STATUS_FAILED and broken.errors and broken.reason
        assert broken.requirements == []
        assert all(not Path(path).exists() for path in created)

    def test_needs_ocr_is_reported_without_running_ocr(self, tmp_path, monkeypatch):
        def refuse_ocr(*_args, **_kwargs):
            raise AssertionError("OCR")

        monkeypatch.setattr(service, "analyze_document", refuse_ocr)
        payload = sd.write_image_only_pdf(tmp_path / "scan.pdf").read_bytes()
        job = service.analyze_job_input(filename="scan.pdf", data=payload)
        assert job.status == STATUS_NEEDS_OCR
        assert job.reason
        assert job.requirements == []
        report = service.compare_with_resume(ResumeAnalysis(status=STATUS_SUCCESS, text_length=80), job)
        level, message = job_feedback(job, report)
        assert report.matches == []
        assert level == "warning" and "OCR was not run" in message

    def test_oversized_upload_is_rejected(self, monkeypatch):
        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 32)
        job = service.analyze_job_input(filename="big.txt", data=b"x" * 200)
        assert job.status == STATUS_FAILED
        assert "too large" in (job.reason or "").lower()
        assert config.MAX_FILE_SIZE_MB == 10


class TestJobViewModel:
    def test_four_outcomes_keep_evidence_priority_and_notes(self):
        report = MatchReport(status=STATUS_SUCCESS, matches=[
            _skill_match("Python", "required", "used", "Built a Python API.", OUTCOME_MATCHED),
            _skill_match("SQL", "preferred", "mentioned", "SQL", OUTCOME_MATCHED, category="Databases"),
            RequirementMatch(
                requirement=JobRequirement(
                    kind="skill", priority="required", text="- PyTorch", skill_name="PyTorch",
                    skill_category="AI and Machine Learning",
                ),
                outcome=OUTCOME_RELATED,
                evidence_type="used",
                evidence=[SkillEvidence(section="projects", text="Trained models with TensorFlow.", evidence_type="used", matched_as="TensorFlow")],
                related_skills=["TensorFlow"],
                note="Same category only. Not an exact match.",
            ),
            _skill_match("Pygame", "required", None, "", OUTCOME_MISSING, category="Game Development"),
            RequirementMatch(
                requirement=JobRequirement(
                    kind="experience", priority="unspecified", text="several years of experience",
                    experience_status="indeterminate",
                ),
                outcome=OUTCOME_INDETERMINATE,
                note="The posting does not state a number of years.",
            ),
        ])
        groups = {outcome: rows for outcome, _heading, rows in comparison_groups(report)}
        assert [heading for _outcome, heading, _rows in comparison_groups(report)] == [
            "Matched", "Related, not a match", "Missing", "Not enough information",
        ]
        used = groups[OUTCOME_MATCHED][0]
        mentioned = groups[OUTCOME_MATCHED][1]
        related = groups[OUTCOME_RELATED][0]
        missing = groups[OUTCOME_MISSING][0]
        unclear = groups[OUTCOME_INDETERMINATE][0]

        assert used.priority == "required" and used.evidence_type == "used"
        assert used.evidence_lines == ["Built a Python API."]
        assert "Resume line: Built a Python API." in used.display_lines()
        assert mentioned.evidence_type == "mentioned" and mentioned.priority == "preferred"
        assert related.evidence_lines == [] and related.evidence_type is None
        assert related.related_skills == ["TensorFlow"]
        assert "not a match" in " ".join(related.display_lines())
        assert missing.evidence_lines == [] and missing.label == "Pygame"
        assert unclear.note == "The posting does not state a number of years."
        assert unclear.priority == "unspecified"
        assert len(groups[OUTCOME_MATCHED]) == report.matched_count == 2
        assert report.related_count == 1
        assert "proficiency" not in ComparisonRowFields()

    def test_feedback_for_empty_and_failed_postings(self):
        empty_job = service.analyze_job_input("")
        resume = ResumeAnalysis(status=STATUS_SUCCESS, text_length=80)
        empty_report = service.compare_with_resume(resume, empty_job)
        level, message = job_feedback(empty_job, empty_report)
        assert empty_report.matches == []
        assert level == "warning" and empty_job.reason in message

        failed_job = service.analyze_job_input(filename="notes.rtf", data=b"{\\rtf1 hi}")
        failed_report = service.compare_with_resume(resume, failed_job)
        level, message = job_feedback(failed_job, failed_report)
        assert level == "error" and "unsupported" in message.lower()


def ComparisonRowFields():
    from web.view_model import ComparisonRow
    return ComparisonRow.__dataclass_fields__


class TestJobPage:
    def test_page_asks_for_a_resume_before_comparison(self):
        text = _visible(_start())
        assert "Analyze a resume first." in text
        assert "Compare with resume" not in text

    def test_pasted_posting_shows_all_four_outcomes_and_evidence(self):
        at = _with_resume()
        at.text_area[0].set_value(JOB_TEXT)
        at = _click(at, "Compare with resume")
        assert not at.exception
        text = _visible(at)
        assert "Python · required · used" in text
        assert "Resume line:" in text and "Python" in text
        assert "PyTorch · preferred · related, not a match" in text
        assert "Pygame · required" in text
        assert "Related, not a match" in text
        assert "Not enough information" in text
        assert "number of years" in text
        report = at.session_state["job_report"]
        assert report.matched_count == sum(item.outcome == OUTCOME_MATCHED for item in report.matches)
        assert any(item.requirement.skill_name == "PyTorch" and item.outcome == OUTCOME_RELATED for item in report.matches)
        assert all(item.outcome != OUTCOME_MATCHED for item in report.matches if item.related_skills)
        assert all("score" not in (metric.label or "").lower() for metric in at.metric)
        assert "hiring probability" not in text.lower()

    def test_empty_paste_and_malformed_file_show_reasons(self):
        at = _click(_with_resume(), "Compare with resume")
        assert not at.exception
        assert "No meaningful text was found" in _visible(at)
        assert at.session_state["job_report"].matches == []

        at = _with_resume()
        job_uploader = next(item for item in at.file_uploader if item.label == "Job description file")
        job_uploader.upload("broken.pdf", b"%PDF-1.4 garbage", "application/pdf")
        at = _click(at, "Compare with resume")
        assert not at.exception
        assert at.session_state["job_analysis"].status == STATUS_FAILED
        assert at.error

    def test_new_upload_clears_the_comparison(self):
        at = _with_resume()
        at.text_area[0].set_value("Requirements\n- Python\n")
        at = _click(at, "Compare with resume")
        assert at.session_state["job_report"] is not None
        at = _click(at, "New upload")
        assert at.session_state["analysis"] is None
        assert at.session_state["job_report"] is None
        assert "Python · required · used" not in _visible(at)
