"""Parser, validation and text-cleaning tests (fixtures are generated in tmp folders)."""
import pytest

import config
import sample_data as sd
from parsers import parse_document, validate_file
from schemas import STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, PARSE_OK
from utils.text_cleaner import count_meaningful_chars, has_meaningful_text, normalize_text


# ---------------------------------------------------------------- text cleaner
class TestTextCleaner:
    def test_collapses_spaces_and_trims_lines(self):
        assert normalize_text("  Hello    world \t ") == "Hello world"

    def test_preserves_paragraph_boundaries_but_collapses_blank_runs(self):
        out = normalize_text("Para one\n\n\n\n\nPara two\nline two")
        assert out == "Para one\n\nPara two\nline two"

    def test_converts_bullet_glyphs(self):
        assert normalize_text("• Built things\n▪ Tested things") == "- Built things\n- Tested things"

    def test_joins_lone_bullet_with_next_line(self):
        assert normalize_text("•\nBuilt a thing") == "- Built a thing"

    def test_normalises_ligatures_nbsp_and_zero_width(self):
        assert normalize_text("ﬁnal\u00a0year\u200b project") == "final year project"

    def test_empty_and_none_like_input(self):
        assert normalize_text("") == ""
        assert normalize_text("   \n\n  ") == ""

    def test_meaningful_text_counts_letters_and_digits_only(self):
        assert count_meaningful_chars("a b-c 1!") == 4
        assert not has_meaningful_text("--- \n ... ")
        assert has_meaningful_text("x" * 60)


# ------------------------------------------------------------------ validation
class TestValidation:
    def test_missing_file(self, tmp_path):
        r = parse_document(tmp_path / "nope.pdf")
        assert r.status == STATUS_FAILED and "not found" in r.errors[0].lower()

    def test_directory_is_rejected(self, tmp_path):
        r = parse_document(tmp_path)
        assert r.status == STATUS_FAILED

    def test_unsupported_extension(self, tmp_path):
        f = tmp_path / "resume.doc"
        f.write_bytes(b"data")
        r = parse_document(f)
        assert r.status == STATUS_FAILED and "unsupported" in r.errors[0].lower()

    def test_zero_byte_file(self, tmp_path):
        f = tmp_path / "empty.pdf"
        f.write_bytes(b"")
        r = parse_document(f)
        assert r.status == STATUS_FAILED and "empty" in r.errors[0].lower()

    def test_oversized_file(self, tmp_path, monkeypatch):
        f = tmp_path / "big.txt"
        f.write_text("x" * 5000)
        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 1000)
        path, errors = validate_file(f)
        assert path is None and "too large" in errors[0].lower()

    def test_extension_check_is_case_insensitive(self, tmp_path):
        f = sd.write_txt(tmp_path / "RESUME.TXT", sd.FULL_RESUME)
        assert parse_document(f).status == PARSE_OK


# ------------------------------------------------------------------ plain text
class TestTextFiles:
    def test_utf8(self, tmp_path):
        r = parse_document(sd.write_txt(tmp_path / "r.txt", sd.FULL_RESUME))
        assert r.status == PARSE_OK and r.source_format == "text" and "Alex Morgan" in r.text

    def test_utf8_bom(self, tmp_path):
        f = tmp_path / "bom.txt"
        f.write_bytes(b"\xef\xbb\xbf" + sd.FULL_RESUME.encode("utf-8"))
        assert parse_document(f).text.startswith("Alex Morgan")

    def test_cp1252_fallback(self, tmp_path):
        f = tmp_path / "latin.txt"
        f.write_bytes(("Jos\u00e9 Garc\u00eda " + "x" * 80).encode("cp1252"))
        assert "Jos\u00e9" in parse_document(f).text

    def test_binary_content_rejected(self, tmp_path):
        f = tmp_path / "bin.txt"
        f.write_bytes(b"\x00\x01\x02" * 100)
        assert parse_document(f).status == STATUS_FAILED

    def test_whitespace_only_is_empty(self, tmp_path):
        f = tmp_path / "ws.txt"
        f.write_text("   \n\n  \n")
        assert parse_document(f).status == STATUS_EMPTY


# ------------------------------------------------------------------------ DOCX
class TestDocx:
    def test_paragraphs(self, tmp_path):
        r = parse_document(sd.write_docx(tmp_path / "r.docx", sd.FULL_RESUME))
        assert r.status == PARSE_OK and r.source_format == "docx"
        assert "Bachelor of Science" in r.text

    def test_table_content_is_extracted_in_order(self, tmp_path):
        r = parse_document(sd.write_docx_with_table(tmp_path / "t.docx"))
        assert r.status == PARSE_OK
        assert "Languages | Python, Java" in r.text
        assert r.text.index("Skills") < r.text.index("Python, Java") < r.text.index("Education")

    def test_empty_docx(self, tmp_path):
        r = parse_document(sd.write_empty_docx(tmp_path / "e.docx"))
        assert r.status == STATUS_EMPTY and r.warnings

    def test_malformed_docx(self, tmp_path):
        f = tmp_path / "bad.docx"
        f.write_bytes(b"this is not a zip archive")
        r = parse_document(f)
        assert r.status == STATUS_FAILED and "corrupted" in r.errors[0].lower()

    def test_truncated_docx(self, tmp_path):
        good = sd.write_docx(tmp_path / "good.docx", sd.FULL_RESUME)
        bad = tmp_path / "trunc.docx"
        bad.write_bytes(good.read_bytes()[:300])
        assert parse_document(bad).status == STATUS_FAILED


# ------------------------------------------------------------------------- PDF
class TestPdf:
    def test_text_pdf(self, tmp_path):
        r = parse_document(sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME))
        assert r.status == PARSE_OK and r.source_format == "pdf" and r.page_count == 1
        assert "alex.morgan@example.com" in r.text and "Bachelor of Science" in r.text

    def test_paragraph_gaps_are_preserved(self, tmp_path):
        r = parse_document(sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME))
        assert "\n\n" in r.text

    def test_multi_page_pdf(self, tmp_path):
        long_text = (sd.FULL_RESUME + "\n") * 4
        r = parse_document(sd.write_pdf(tmp_path / "long.pdf", long_text))
        assert r.status == PARSE_OK and r.page_count >= 2

    def test_image_only_pdf_needs_ocr(self, tmp_path):
        r = parse_document(sd.write_image_only_pdf(tmp_path / "scan.pdf"))
        assert r.status == STATUS_NEEDS_OCR
        assert r.text == ""                                  # never pretend extraction worked
        assert any("OCR" in w and "Phase 2" in w for w in r.warnings)

    def test_encrypted_pdf(self, tmp_path):
        r = parse_document(sd.write_encrypted_pdf(tmp_path / "enc.pdf"))
        assert r.status == STATUS_FAILED and "password" in r.errors[0].lower()

    def test_malformed_pdf(self, tmp_path):
        f = tmp_path / "bad.pdf"
        f.write_bytes(b"%PDF-1.4 this is garbage and not a real pdf")
        r = parse_document(f)
        assert r.status == STATUS_FAILED and r.errors

    def test_pdf_with_almost_no_text_needs_ocr(self, tmp_path):
        import pymupdf
        f = tmp_path / "tiny.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((60, 60), "Hi there", fontsize=10)
        doc.save(str(f))
        doc.close()
        assert parse_document(f).status == STATUS_NEEDS_OCR

    def test_page_limit_warning(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_PDF_PAGES", 1)
        r = parse_document(sd.write_pdf(tmp_path / "long.pdf", (sd.FULL_RESUME + "\n") * 4))
        assert any("only the first 1" in w for w in r.warnings)
