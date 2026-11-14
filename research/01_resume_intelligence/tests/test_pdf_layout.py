"""Layout regressions: columns, repeated margins, DOCX headers and footers.

Phase 1 single-column extraction must stay free of column warnings.
"""
import pymupdf
import pytest

import sample_data as sd
from parsers import parse_document
from parsers.pdf_layout import TextLine, detect_vertical_gutter, order_lines_for_columns
from schemas import PARSE_OK, STATUS_NEEDS_OCR


def _word(x0, x1, text="word"):
    return (x0, 10, x1, 20, text, 0, 0, 0)


class TestGutterHeuristic:
    def test_two_clusters_have_a_gutter(self):
        words = [_word(40, 120) for _ in range(12)] + [_word(420, 520) for _ in range(12)]
        gutter = detect_vertical_gutter(words, page_width=600)
        assert gutter is not None
        assert 180 < gutter < 420

    def test_full_width_lines_are_not_split(self):
        words = []
        for index in range(20):
            words.append(_word(40 + index * 25, 60 + index * 25, text=f"w{index}"))
        assert detect_vertical_gutter(words, page_width=600) is None

    def test_column_order_is_left_then_right(self):
        lines = [
            TextLine(80, 92, 40, 180, "Skills"),
            TextLine(80, 92, 360, 520, "Education"),
            TextLine(110, 122, 40, 200, "Python SQL"),
            TextLine(110, 122, 360, 540, "Bachelor of Science"),
        ]
        ordered = order_lines_for_columns(lines, gutter_x=280, page_width=600)
        assert [line.text for line in ordered] == [
            "Skills", "Python SQL", "Education", "Bachelor of Science",
        ]


def _write_two_column_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    left = ["Skills", "Python SQL Git Docker", "Flask Linux Java React", "Built internal API services"]
    right = ["Education", "Bachelor of Science", "Example University", "Graduated in 2024"]
    y = 90
    for line in left:
        page.insert_text((50, y), line, fontsize=12, fontname="helv")
        y += 32
    y = 90
    for line in right:
        page.insert_text((360, y), line, fontsize=12, fontname="helv")
        y += 32
    doc.save(str(path))
    doc.close()
    return path


def _write_margin_pdf(path):
    doc = pymupdf.open()
    bodies = ("BodyAlpha unique paragraph about Python and Django services.",
              "BodyBeta unique paragraph about Docker and SQL analysis.",
              "BodyGamma unique paragraph about Flask and Git practice.")
    for body in bodies:
        page = doc.new_page()
        page.insert_text((72, 36), "Synthetic Header", fontsize=9, fontname="helv")
        page.insert_text((72, 220), body, fontsize=12, fontname="helv")
        page.insert_text((72, 830), "Page footer note", fontsize=9, fontname="helv")
    doc.save(str(path))
    doc.close()
    return path


class TestPdfLayoutExtraction:
    def test_single_column_resume_is_not_reordered(self, tmp_path):
        parsed = parse_document(sd.write_pdf(tmp_path / "r.pdf", sd.FULL_RESUME))
        assert parsed.status == PARSE_OK
        assert not any("multi-column" in warning for warning in parsed.warnings)
        assert "alex.morgan@example.com" in parsed.text
        assert "\n\n" in parsed.text

    def test_two_column_page_is_read_left_then_right(self, tmp_path):
        parsed = parse_document(_write_two_column_pdf(tmp_path / "cols.pdf"))
        assert parsed.status == PARSE_OK, parsed.warnings
        text = parsed.text
        assert text.index("Skills") < text.index("Python") < text.index("Education"), text
        assert text.index("Education") < text.index("Bachelor"), text
        assert any("multi-column" in warning for warning in parsed.warnings)

    def test_repeated_margin_text_is_kept_once(self, tmp_path):
        parsed = parse_document(_write_margin_pdf(tmp_path / "margins.pdf"))
        assert parsed.status == PARSE_OK, parsed.errors
        assert parsed.text.count("Synthetic Header") == 1
        assert parsed.text.count("Page footer note") == 1
        assert "BodyAlpha" in parsed.text and "BodyBeta" in parsed.text and "BodyGamma" in parsed.text
        assert any("header/footer" in warning for warning in parsed.warnings)

    def test_image_only_pdf_still_needs_ocr(self, tmp_path):
        parsed = parse_document(sd.write_image_only_pdf(tmp_path / "scan.pdf"))
        assert parsed.status == STATUS_NEEDS_OCR
        assert parsed.text == ""
        assert any("Phase 2" in warning for warning in parsed.warnings)


class TestDocxMargins:
    def test_duplicate_header_is_not_repeated_and_page_number_is_dropped(self, tmp_path):
        import docx

        path = tmp_path / "headed.docx"
        document = docx.Document()
        section = document.sections[0]
        section.header.paragraphs[0].text = "Taylor Reed"
        section.header.add_paragraph("taylor.reed@example.com")
        section.footer.paragraphs[0].text = "Page 1"
        section.footer.add_paragraph("Portfolio available on request")
        document.add_paragraph("Taylor Reed")
        document.add_paragraph("Skills")
        document.add_paragraph("Python, SQL, Git, Docker, Flask, Linux")
        document.save(str(path))

        parsed = parse_document(path)
        assert parsed.status == PARSE_OK
        assert parsed.text.count("Taylor Reed") == 1
        assert "taylor.reed@example.com" in parsed.text
        assert "Page 1" not in parsed.text
        assert "Portfolio available on request" in parsed.text
        assert parsed.text.index("taylor.reed@example.com") < parsed.text.index("Skills")
        assert any("Footer text" in warning for warning in parsed.warnings)
