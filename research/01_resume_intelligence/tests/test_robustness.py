"""Robustness cases that the earlier suites did not already lock down.

Malformed files, encrypted PDFs, empty text, missing headings, and a missing
Tesseract install are covered in ``test_parsers.py``, ``test_pipeline.py``, and
``test_phase2_extraction.py``. This module adds the gaps found in the Phase 3
audit: period-terminated headings, accented locations, hyphen-broken OCR text,
and Phase 2 rejection of oversized, unsupported, and encrypted files.
"""
import config
import sample_data as sd
from extraction.text_merge import repair_ocr_text
from pipeline import analyze_document, analyze_resume, analyze_text
from schemas import STATUS_EMPTY, STATUS_FAILED, STATUS_PARTIAL, STATUS_SUCCESS


_DOTTED = """\
Alex Morgan
alex.morgan@example.com

Skills.
Python, Django, Docker, SQL

Experience.
Backend Developer, Sample Labs
- Built APIs with Python and Docker

Education.
BS Computer Science, Example University (2018 - 2022)
"""

_UNICODE = """\
José García
jose.garcia@example.com | São Paulo, Brazil

S K I L L S
Python, Django, Docker, SQL

=== Experience ===
Backend Developer, Sample Labs
- Built APIs with Python and Docker for client projects
"""


class TestLayoutAndUnicode:
    def test_period_terminated_headings_still_split_sections(self):
        analysis = analyze_text(_DOTTED)
        assert analysis.status == STATUS_SUCCESS
        assert [section.name for section in analysis.sections] == [
            "header", "skills", "experience", "education",
        ]
        assert analysis.experience[0].title == "Backend Developer"
        assert analysis.education[0].degree == "BS"
        assert {"Python", "Django", "Docker", "SQL"} <= {skill.name for skill in analysis.skills}

    def test_spaced_and_decorated_headings(self):
        analysis = analyze_text(_UNICODE)
        assert analysis.status == STATUS_SUCCESS
        assert analysis.contact.name == "José García"
        assert analysis.contact.email == "jose.garcia@example.com"
        assert analysis.contact.location == "São Paulo, Brazil"
        assert "experience" in {section.name for section in analysis.sections}
        assert analysis.experience[0].organization == "Sample Labs"

    def test_unicode_text_file_round_trip(self, tmp_path):
        path = tmp_path / "resume.txt"
        path.write_text(_UNICODE, encoding="utf-8")
        analysis = analyze_resume(path)
        assert analysis.status == STATUS_SUCCESS
        assert analysis.contact.name == "José García"
        assert analysis.contact.location == "São Paulo, Brazil"

    def test_unknown_heading_stays_partial_and_invents_nothing(self):
        text = (
            "Alex Morgan\nalex.morgan@example.com\n\n"
            "Where I Have Worked\nBackend Developer, Sample Labs\n"
            "- Built APIs with Python and Docker and SQL and Flask\n"
        )
        analysis = analyze_text(text)
        assert analysis.status == STATUS_PARTIAL
        assert analysis.experience == []
        assert "Python" in {skill.name for skill in analysis.skills}


class TestLittleText:
    def test_whitespace_file_is_empty(self, tmp_path):
        path = tmp_path / "blank.txt"
        path.write_text(" \n\n\t\n", encoding="utf-8")
        analysis = analyze_resume(path)
        assert analysis.status == STATUS_EMPTY
        assert analysis.skills == [] and analysis.errors == []

    def test_very_short_file_is_empty(self, tmp_path):
        path = tmp_path / "tiny.txt"
        path.write_text("hello\n", encoding="utf-8")
        analysis = analyze_document(path)
        assert analysis.status == STATUS_EMPTY
        assert analysis.skills == []


class TestOcrTextErrors:
    def test_hyphen_breaks_are_rejoined_before_skill_extraction(self):
        raw = (
            "Alex Morgan\nalex.morgan@example.com\n\n"
            "Skills\nPy-\nthon, Django, Dock-\ner, SQL\n\n"
            "Experience\nBuilt services with Python and Docker for internal tools\n"
        )
        analysis = analyze_text(repair_ocr_text(raw), source_format="ocr")
        assert analysis.status == STATUS_SUCCESS
        assert {"Python", "Django", "Docker", "SQL"} <= {skill.name for skill in analysis.skills}

    def test_digit_substitutions_are_not_rewritten_into_skills(self):
        text = (
            "Alex Morgan\nalex.morgan@example.com\n\n"
            "Skills\nPyth0n, Djang0, Dock3r\n\n"
            "Experience\nBuilt services with Flask and SQL for internal tools\n"
        )
        analysis = analyze_text(repair_ocr_text(text), source_format="ocr")
        names = {skill.name for skill in analysis.skills}
        assert "Python" not in names and "Django" not in names and "Docker" not in names
        assert {"Flask", "SQL"} <= names


class TestPhase2Rejection:
    def test_oversized_file_fails_and_the_ten_megabyte_limit_stays(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 32)
        path = tmp_path / "big.txt"
        path.write_text("x" * 200, encoding="utf-8")
        analysis = analyze_document(path)
        assert analysis.status == STATUS_FAILED
        assert "too large" in analysis.errors[0].lower()
        assert config.MAX_FILE_SIZE_MB == 10

    def test_unsupported_formats_fail(self, tmp_path):
        for name in ("resume.rtf", "scan.gif", "notes.doc"):
            path = tmp_path / name
            path.write_bytes(b"not a supported resume")
            analysis = analyze_document(path)
            assert analysis.status == STATUS_FAILED, name
            assert "unsupported" in analysis.errors[0].lower()

    def test_encrypted_pdf_fails_on_the_phase2_path(self, tmp_path):
        analysis = analyze_document(sd.write_encrypted_pdf(tmp_path / "secret.pdf"))
        assert analysis.status == STATUS_FAILED
        assert analysis.errors
        assert analysis.skills == []

    def test_missing_and_malformed_files_do_not_raise(self, tmp_path):
        missing = analyze_document(tmp_path / "absent.pdf")
        assert missing.status == STATUS_FAILED and missing.errors
        garbage = tmp_path / "broken.pdf"
        garbage.write_bytes(b"%PDF-1.4 this is not a real document")
        broken = analyze_document(garbage)
        assert broken.status == STATUS_FAILED and broken.errors
