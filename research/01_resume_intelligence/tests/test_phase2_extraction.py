"""Phase 2 extraction, provenance, OCR error handling and Phase 1 compatibility."""
import json

import cv2
import numpy as np
import pytest

import sample_data as sd
from errors import TesseractUnavailable
from extraction.text_merge import combine_native_and_ocr, included_text, mark_duplicate_pages, repair_ocr_text
from extraction.unified import extract_document, page_needs_ocr
from ocr.tesseract_ocr import OcrResult, OcrSettings, install_hint, locate_tesseract, ocr_image, recognize_image
from parsers import parse_document
from pipeline import analyze_document, analyze_resume
from schemas import STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_SUCCESS
from test_pipeline import run_cli


def _png(path, width=80, height=80, value=255):
    image = np.full((height, width, 3), value, np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())
    return path


def _diagnostics():
    return {
        "winner": "grayscale",
        "estimated_skew_degrees": 0.0,
        "applied_rotation_degrees": 0.0,
        "steps": ["grayscale"],
        "notes": [],
        "candidates": [],
        "attempts": [],
    }


OCR_TEXT = """Alex Morgan
alex.morgan@example.com

Skills
Python, Django, Docker, SQL, Git, Flask

Experience
Software Engineering Intern at Acme Software Solutions
- Built REST API endpoints with Django and PostgreSQL
"""


class TestPhase1Contract:
    def test_phase1_json_omits_phase2_fields(self, tmp_path):
        analysis = analyze_resume(sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME))
        data = json.loads(analysis.to_json())
        assert "text_provenance" not in data
        assert "quality_report" not in data
        assert data["schema_version"] == "1.0"
        assert data["contact"]["email"] == "alex.morgan@example.com"

    def test_analyze_resume_does_not_call_ocr(self, tmp_path, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("Phase 1 analyze_resume must not run OCR")

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", boom)
        analysis = analyze_resume(sd.write_image_only_pdf(tmp_path / "scan.pdf"))
        assert analysis.status == STATUS_NEEDS_OCR
        assert analysis.skills == [] and analysis.text_length == 0

    def test_png_is_still_unsupported_for_phase1(self, tmp_path):
        parsed = parse_document(_png(tmp_path / "page.png"))
        assert parsed.status == STATUS_FAILED
        assert "unsupported" in parsed.errors[0].lower()

    def test_default_cli_summary_has_no_text_sources(self, tmp_path):
        path = sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME)
        result = run_cli(path)
        assert result.returncode == 0
        assert "Text sources" not in result.stdout
        assert "Status:  SUCCESS" in result.stdout


class TestNativeDocumentPath:
    def test_text_pdf_matches_phase1_and_skips_ocr(self, tmp_path, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("A text PDF should not be sent to OCR")

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", boom)
        path = sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME)
        phase1 = analyze_resume(path)
        phase2 = analyze_document(path)
        assert phase2.status == STATUS_SUCCESS
        assert phase2.source_format == "pdf"
        assert {skill.name for skill in phase2.skills} == {skill.name for skill in phase1.skills}
        assert phase2.contact == phase1.contact
        assert [item.method for item in phase2.text_provenance] == ["native_pdf"]
        assert phase2.quality_report is not None
        assert any(item.code == "ats_compatibility" and item.kind == "unsupported"
                   for item in phase2.quality_report.findings)
        data = json.loads(phase2.to_json())
        assert data["text_provenance"][0]["method"] == "native_pdf"
        assert all("this resume is ATS-incompatible" not in item.message.lower()
                   for item in phase2.quality_report.findings)

    def test_docx_and_txt_provenance(self, tmp_path):
        docx = analyze_document(sd.write_docx(tmp_path / "r.docx", sd.FULL_RESUME), ocr=False)
        text = analyze_document(sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME), ocr=False)
        assert docx.status == STATUS_SUCCESS and docx.text_provenance[0].method == "native_docx"
        assert text.status == STATUS_SUCCESS and text.text_provenance[0].method == "native_text"
        assert "Python" in {skill.name for skill in text.skills}

    def test_ocr_flag_on_text_file_does_not_need_tesseract(self, tmp_path):
        path = sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME)
        result = run_cli(path, "--ocr", "--json")
        assert result.returncode == 0, result.stdout
        data = json.loads(result.stdout)
        assert data["text_provenance"][0]["method"] == "native_text"
        assert data["contact"]["name"] == "Alex Morgan"


class TestDuplicatePrevention:
    def test_overlapping_ocr_is_dropped(self):
        native = "Python Django Docker SQL Git Flask experience building APIs for clients"
        pieces = combine_native_and_ocr(native, native, ocr_confidence=90)
        assert included_text(pieces).count("Python") == 1
        assert any(piece.suppressed_duplicate and piece.method == "ocr" for piece in pieces)

    def test_ocr_that_adds_text_replaces_a_short_native_fragment(self):
        native = "Python Django"
        ocr = "Python Django Docker SQL Git Flask Linux React PostgreSQL scikit learn NLTK"
        pieces = combine_native_and_ocr(native, ocr, ocr_confidence=70)
        text = included_text(pieces)
        assert "Flask" in text and text.count("Python") == 1
        assert any(piece.suppressed_duplicate and piece.method == "native_pdf" for piece in pieces)

    def test_different_text_is_kept(self):
        pieces = combine_native_and_ocr("Python Django Docker SQL", "Education Bachelor University Degree", ocr_confidence=50)
        text = included_text(pieces)
        assert "Python" in text and "Education" in text

    def test_hyphen_repair_does_not_touch_phase1_cleaner(self):
        assert repair_ocr_text("develop-\nment with Python") == "development with Python"
        assert repair_ocr_text("AI-ML\nstack") == "AI-ML\nstack"

    def test_repeated_pdf_page_is_included_once(self, tmp_path, monkeypatch):
        def boom(*_args, **_kwargs):
            raise AssertionError("Both pages have native text")

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", boom)
        import pymupdf
        path = tmp_path / "dup.pdf"
        doc = pymupdf.open()
        for _ in range(2):
            page = doc.new_page()
            page.insert_text((72, 140), "Duplicate detection uses Python Django Docker SQL.", fontsize=12, fontname="helv")
            page.insert_text((72, 170), "Git Flask Linux React support this synthetic page.", fontsize=12, fontname="helv")
        doc.save(str(path))
        doc.close()
        extracted = extract_document(path)
        assert extracted.text.lower().count("duplicate detection") == 1
        assert any("repeats the previous page" in warning for warning in extracted.warnings)
        assert any(record.suppressed_duplicate for record in extracted.pages)

    def test_page_needs_ocr_rules(self):
        assert page_needs_ocr(0, 0.0) is True
        assert page_needs_ocr(500, 0.9) is False
        assert page_needs_ocr(100, 0.0) is False
        assert page_needs_ocr(100, 0.8) is True


class TestOcrFailures:
    def test_scanned_pdf_failure_drops_the_phase1_future_ocr_warning(self, tmp_path):
        analysis = analyze_document(
            sd.write_image_only_pdf(tmp_path / "scan.pdf"),
            tesseract_cmd=r"C:\missing\tesseract.exe",
        )
        assert analysis.status == STATUS_FAILED
        assert any("Tesseract" in error for error in analysis.errors)
        joined = " ".join(analysis.warnings)
        assert "will be added" not in joined
        assert "No resume data was extracted" not in joined

    def test_ocr_off_scan_uses_the_phase2_message(self, tmp_path):
        analysis = analyze_document(sd.write_image_only_pdf(tmp_path / "scan.pdf"), ocr=False)
        assert analysis.status == STATUS_NEEDS_OCR
        assert any("turned off" in warning.lower() for warning in analysis.warnings)
        assert all("will be added" not in warning for warning in analysis.warnings)
        assert all("No resume data was extracted" not in warning for warning in analysis.warnings)

    def test_missing_tesseract_is_an_error_not_a_crash(self, tmp_path, monkeypatch):
        message = "Tesseract OCR is not installed. " + install_hint()
        monkeypatch.setattr("ocr.tesseract_ocr.locate_tesseract", lambda explicit=None: (None, message))
        analysis = analyze_document(_png(tmp_path / "scan.png", 200, 160))
        assert analysis.status == STATUS_FAILED
        assert analysis.skills == []
        assert any("Tesseract" in error for error in analysis.errors)
        assert any("TESSERACT_CMD" in error or "UB-Mannheim" in error for error in analysis.errors)

    def test_require_tesseract_raises(self, monkeypatch):
        monkeypatch.setattr("ocr.tesseract_ocr.locate_tesseract", lambda explicit=None: (None, "missing"))
        from ocr.tesseract_ocr import require_tesseract
        with pytest.raises(TesseractUnavailable):
            require_tesseract(None)

    def test_bad_explicit_path(self):
        path, message = locate_tesseract(r"C:\missing\tesseract.exe")
        assert path is None
        assert "not found" in message.lower()
        assert "Tesseract" in message

    def test_empty_ocr_is_not_a_failure(self, monkeypatch):
        monkeypatch.setattr("ocr.tesseract_ocr._run_tesseract", lambda image, settings: ("", []))
        result = recognize_image(np.full((40, 40), 255, np.uint8), OcrSettings())
        assert result.status == "empty" and result.error is None

    def test_empty_image_analysis(self, tmp_path, monkeypatch):
        def fake(image, settings, page_number=None):
            return OcrResult(status="empty", text="", warnings=["OCR ran but returned no readable text."]), _diagnostics()

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", fake)
        analysis = analyze_document(_png(tmp_path / "blank.png"))
        assert analysis.status == STATUS_EMPTY
        assert analysis.skills == []
        assert any("clearer" in error.lower() for error in analysis.errors)
        assert any("no readable text" in warning.lower() for warning in analysis.warnings)

    def test_ocr_exception_is_captured(self, monkeypatch):
        def boom(image, settings):
            raise RuntimeError("engine blew up")

        monkeypatch.setattr("ocr.tesseract_ocr._run_tesseract", boom)
        result = recognize_image(np.full((40, 40), 255, np.uint8))
        assert result.status == "failed" and "engine blew up" in result.error

    def test_failed_ocr_on_an_image(self, tmp_path, monkeypatch):
        def fake(image, settings, page_number=None):
            return OcrResult(status="failed", error="Tesseract failed: engine blew up", error_code="tesseract_failed"), _diagnostics()

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", fake)
        analysis = analyze_document(_png(tmp_path / "page.png"))
        assert analysis.status == STATUS_FAILED
        assert any("engine blew up" in error for error in analysis.errors)

    def test_engine_failure_is_not_retried(self, monkeypatch):
        calls = {"n": 0}

        def fake(image, settings=None):
            calls["n"] += 1
            return OcrResult(status="failed", error="missing", error_code="tesseract_missing")

        monkeypatch.setattr("ocr.tesseract_ocr.recognize_image", fake)
        result, diagnostics = ocr_image(np.full((70, 90, 3), 255, np.uint8))
        assert result.status == "failed"
        assert calls["n"] == 1
        assert diagnostics["candidates"]

    def test_invalid_and_corrupt_inputs(self, tmp_path):
        empty = tmp_path / "empty.png"
        empty.write_bytes(b"")
        assert analyze_document(empty).status == STATUS_FAILED

        bad = tmp_path / "bad.png"
        bad.write_bytes(b"not-an-image")
        bad_result = analyze_document(bad)
        assert bad_result.status == STATUS_FAILED and bad_result.errors

        pdf = tmp_path / "bad.pdf"
        pdf.write_bytes(b"%PDF-1.4 this is garbage")
        assert analyze_document(pdf).status == STATUS_FAILED

        docx = tmp_path / "bad.docx"
        docx.write_bytes(b"this is not a zip")
        assert analyze_document(docx).status == STATUS_FAILED


class TestPipelineIntegration:
    def test_fake_ocr_reaches_skill_extraction(self, tmp_path, monkeypatch):
        def fake(image, settings, page_number=None):
            assert page_number == 1
            return OcrResult(text=OCR_TEXT, status="ok", mean_confidence=88.0), _diagnostics()

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", fake)
        analysis = analyze_document(_png(tmp_path / "resume.png", 320, 400))
        assert analysis.status == STATUS_SUCCESS
        assert analysis.source_format == "image"
        assert analysis.text_provenance[0].method == "ocr"
        assert analysis.text_provenance[0].page_number == 1
        assert analysis.text_provenance[0].confidence == 88.0
        assert {"Python", "Django", "Docker"} <= {skill.name for skill in analysis.skills}
        assert analysis.contact.email == "alex.morgan@example.com"
        assert any("not a guarantee" in warning for warning in analysis.warnings)
        codes = {item.code for item in analysis.quality_report.findings}
        assert "low_resolution" in codes
        assert "ats_compatibility" in codes

    def test_mixed_pdf_keeps_page_order(self, tmp_path, monkeypatch):
        import pymupdf
        calls = []

        def fake(image, settings, page_number=None):
            calls.append(page_number)
            return OcrResult(
                text="Projects\nInventory tool using Python and Flask and SQLite\n",
                status="ok",
                mean_confidence=91.0,
            ), _diagnostics()

        monkeypatch.setattr("extraction.unified.ocr_bgr_image", fake)
        path = tmp_path / "mixed.pdf"
        doc = pymupdf.open()
        page = doc.new_page()
        y = 72
        for line in OCR_TEXT.splitlines():
            page.insert_text((72, y), line or " ", fontsize=11, fontname="helv")
            y += 16
        scanned = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 200), False)
        pix.clear_with(255)
        scanned.insert_image(pymupdf.Rect(40, 40, 400, 400), pixmap=pix)
        doc.save(str(path))
        doc.close()

        analysis = analyze_document(path)
        assert calls == [2]
        methods = [(item.page_number, item.method, item.suppressed_duplicate) for item in analysis.text_provenance]
        assert methods[0][0] == 1 and methods[0][1] == "native_pdf"
        assert any(item.page_number == 2 and item.method == "ocr" and not item.suppressed_duplicate
                   for item in analysis.text_provenance)
        assert {"Python", "Flask"} <= {skill.name for skill in analysis.skills}
        assert analysis.status == STATUS_SUCCESS

    def test_duplicate_marker_helper(self):
        sentence = "python django docker sql git flask linux react postgresql nltk sklearn pandas numpy"
        assert mark_duplicate_pages([(1, sentence), (2, sentence)]) == [2]
        assert mark_duplicate_pages([(1, sentence), (2, "education bachelor university degree history")]) == []
