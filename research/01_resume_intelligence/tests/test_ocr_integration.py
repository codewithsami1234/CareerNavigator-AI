"""OCR tests that need a local Tesseract executable.

They are skipped with a reason when Tesseract is not installed. Unit tests in
``test_phase2_extraction.py`` still cover the missing-engine path.
"""
from pathlib import Path

import pymupdf
import pytest

import config
from extraction.unified import extract_document
from ocr.tesseract_ocr import locate_tesseract
from pipeline import analyze_document

pytestmark = pytest.mark.integration

_LINES = (
    "Alex Morgan",
    "alex.morgan@example.com",
    "Skills",
    "Python Django Docker SQL Git Flask",
    "Experience",
    "Built services with Python and Docker",
)


@pytest.fixture(scope="module")
def tesseract_bin():
    path, message = locate_tesseract(None)
    if not path:
        pytest.skip(message)
    return path


def _render_text_image(path: Path) -> None:
    doc = pymupdf.open()
    page = doc.new_page()
    y = 80
    for line in _LINES:
        page.insert_text((72, y), line, fontsize=18, fontname="helv")
        y += 36
    pix = page.get_pixmap(dpi=220, alpha=False)
    pix.save(str(path))
    doc.close()


def _render_scanned_pdf(path: Path, image_path: Path) -> None:
    """Embed the rendered page as a text-free scan under the upload limit.

    ``insert_image`` decodes the PNG, and a default ``save`` writes those
    pixels uncompressed. A 220 DPI RGB page is about 13 MB, over the 10 MB
    limit. Deflate keeps the same pixels and stores a normal compressed scan.
    """
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(page.rect, filename=str(image_path))
    doc.save(str(path), deflate=True, deflate_images=True)
    doc.close()


class TestTesseractIntegration:
    def test_image_resume_reaches_the_phase1_pipeline(self, tmp_path, tesseract_bin):
        image = tmp_path / "resume.png"
        _render_text_image(image)
        extracted = extract_document(image, settings=_settings(tesseract_bin))
        assert extracted.status == "ok", extracted.errors
        assert extracted.pages and extracted.pages[0].method == "ocr"
        lowered = extracted.text.lower()
        found = [token for token in ("python", "django", "docker", "sql", "flask") if token in lowered]
        assert len(found) >= 2, extracted.text

        analysis = analyze_document(image, tesseract_cmd=tesseract_bin)
        assert analysis.status in {"success", "partial"}
        assert analysis.text_provenance[0].method == "ocr"
        assert analysis.skills

    def test_scanned_pdf_uses_ocr(self, tmp_path, tesseract_bin):
        image = tmp_path / "page.png"
        pdf = tmp_path / "scan.pdf"
        _render_text_image(image)
        _render_scanned_pdf(pdf, image)
        assert pdf.stat().st_size <= config.MAX_FILE_SIZE_BYTES, (
            f"{pdf.stat().st_size / (1024 * 1024):.1f} MB exceeds the "
            f"{config.MAX_FILE_SIZE_MB} MB upload limit"
        )
        extracted = extract_document(pdf, settings=_settings(tesseract_bin))
        assert extracted.status == "ok", extracted.errors
        assert any(page.method == "ocr" for page in extracted.pages)
        lowered = extracted.text.lower()
        found = [token for token in ("python", "django", "docker", "sql", "flask") if token in lowered]
        assert len(found) >= 2, extracted.text

        analysis = analyze_document(pdf, tesseract_cmd=tesseract_bin)
        assert analysis.status in {"success", "partial"}
        assert any(item.method == "ocr" for item in analysis.text_provenance)
        assert analysis.skills


def _settings(executable: str):
    from ocr.tesseract_ocr import OcrSettings
    return OcrSettings(tesseract_cmd=executable)
