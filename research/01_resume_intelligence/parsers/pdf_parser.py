"""PDF text extraction with PyMuPDF.

Text-based PDFs are read here. Scans still return status ``needs_ocr`` and an
empty ``ParseResult.text`` so Phase 1 callers are unchanged. ``read_pdf`` keeps
per-page text for the Phase 2 document interface, which OCRs sparse pages.

Two optional layout fixes run only when the evidence is clear:

* a vertical gutter with text on both sides -> read the left column first;
* a short margin line that repeats on later pages -> drop it after page 1.

Single-column pages keep PyMuPDF's original line order.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import config
from parsers.pdf_layout import (
    TextLine, detect_vertical_gutter, join_lines, order_lines_for_columns, strip_repeated_margin_lines,
)
from schemas import DocumentLink, PARSE_OK, ParseResult, STATUS_FAILED, STATUS_NEEDS_OCR
from utils.text_cleaner import count_meaningful_chars

_NEEDS_OCR_WARNING = (
    "This PDF contains little or no extractable text (it is probably a scan or image-only "
    "document). OCR is required. Re-run with --ocr to use the Phase 2 reader. "
    "No resume data was extracted."
)


def _import_pymupdf():
    try:
        import pymupdf  # PyMuPDF >= 1.24.3
        return pymupdf
    except ImportError:
        try:
            import fitz  # older PyMuPDF
            return fitz
        except ImportError:
            return None


@dataclass
class PdfPageContent:
    number: int
    text: str
    char_count: int
    warnings: List[str] = field(default_factory=list)
    column_reordered: bool = False
    image_fraction: float = 0.0


@dataclass
class PdfRead:
    """Page-level PDF read used by Phase 1 ``parse_pdf`` and Phase 2 OCR."""
    text: str = ""
    status: str = PARSE_OK
    page_count: Optional[int] = None
    file_name: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pages: List[PdfPageContent] = field(default_factory=list)
    links: List[DocumentLink] = field(default_factory=list)


def _page_links(page, page_number: int) -> List[DocumentLink]:
    """External URI link annotations with their visible anchor text."""
    links: List[DocumentLink] = []
    try:
        annotations = page.get_links() or []
    except Exception:
        return links
    for item in annotations:
        uri = (item.get("uri") or "").strip()
        if not uri or not uri.lower().startswith(("http://", "https://")):
            continue
        anchor = ""
        rect = item.get("from")
        if rect is not None:
            try:
                anchor = " ".join(page.get_textbox(rect).split())
            except Exception:
                anchor = ""
        links.append(DocumentLink(text=anchor, uri=uri, page_number=page_number))
    return links


def _image_fraction(page) -> float:
    """Share of the page covered by image blocks. 0 when the page is text-only."""
    try:
        area = float(page.rect.width * page.rect.height)
        if area <= 0:
            return 0.0
        data = page.get_text("dict")
        covered = 0.0
        for block in data.get("blocks", []):
            if block.get("type") != 1 or "bbox" not in block:
                continue
            x0, y0, x1, y1 = block["bbox"]
            covered += max(0.0, float(x1) - float(x0)) * max(0.0, float(y1) - float(y0))
        return max(0.0, min(1.0, covered / area))
    except Exception:
        return 0.0


def _page_lines(page) -> Tuple[List[TextLine], list]:
    data = page.get_text("dict", sort=True)
    lines: List[TextLine] = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:      # 0 = text block, 1 = image block
            continue
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", [])).strip()
            if not text:
                continue
            x0, y0, x1, y1 = line["bbox"]
            lines.append(TextLine(float(y0), float(y1), float(x0), float(x1), text))
    try:
        words = page.get_text("words") or []
    except Exception:
        words = []
    return lines, list(words)


def _compose_page(lines: Sequence[TextLine], words: Sequence, page_width: float) -> Tuple[str, bool]:
    """Return page text and whether a column reorder was applied."""
    gutter = detect_vertical_gutter(words, page_width)
    if gutter is None:
        return join_lines(lines), False
    ordered = order_lines_for_columns(lines, gutter, page_width)
    return join_lines(ordered), True


def read_pdf(path: Path) -> PdfRead:
    """Open a PDF and return per-page text plus the same status ``parse_pdf`` uses."""
    result = PdfRead(file_name=path.name)
    pm = _import_pymupdf()
    if pm is None:
        result.status = STATUS_FAILED
        result.errors.append("PyMuPDF is not installed. Run: pip install -r requirements.txt")
        return result

    try:
        doc = pm.open(str(path))
    except Exception as exc:
        result.status = STATUS_FAILED
        result.errors.append(
            f"Could not open PDF (file is corrupted or not a real PDF): {exc.__class__.__name__}"
        )
        return result

    try:
        if doc.needs_pass:
            if not doc.authenticate(""):
                result.status = STATUS_FAILED
                result.errors.append("The PDF is password-protected/encrypted and cannot be read.")
                return result

        result.page_count = doc.page_count
        if doc.page_count == 0:
            result.status = STATUS_FAILED
            result.errors.append("The PDF contains no pages.")
            return result

        pages_to_read = min(doc.page_count, config.MAX_PDF_PAGES)
        if doc.page_count > pages_to_read:
            result.warnings.append(
                f"The PDF has {doc.page_count} pages; only the first {pages_to_read} were read."
            )

        page_lines: List[List[TextLine]] = []
        page_words: List[list] = []
        page_widths: List[float] = []
        page_heights: List[float] = []
        page_images: List[float] = []
        for index in range(pages_to_read):
            try:
                lines, words = _page_lines(doc[index])
                width = float(doc[index].rect.width)
                height = float(doc[index].rect.height)
                image_fraction = _image_fraction(doc[index])
                result.links.extend(_page_links(doc[index], index + 1))
            except Exception as exc:
                result.warnings.append(f"Page {index + 1} could not be read ({exc.__class__.__name__}).")
                lines, words, width, height, image_fraction = [], [], 0.0, 0.0, 0.0
            page_lines.append(lines)
            page_words.append(words)
            page_widths.append(width)
            page_heights.append(height)
            page_images.append(image_fraction)
    except Exception as exc:
        result.status = STATUS_FAILED
        result.errors.append(f"Unexpected error while reading the PDF: {exc.__class__.__name__}: {exc}")
        return result
    finally:
        try:
            doc.close()
        except Exception:
            pass

    removed = strip_repeated_margin_lines(page_lines, page_heights)
    if removed:
        result.warnings.append(
            f"Repeated header/footer text was removed from pages after the first ({removed} line(s))."
        )

    page_texts: List[str] = []
    sparse_pages = 0
    for index, lines in enumerate(page_lines):
        text, reordered = _compose_page(lines, page_words[index], page_widths[index])
        warnings: List[str] = []
        if reordered:
            message = (
                f"Page {index + 1}: a multi-column reading-order heuristic was applied. "
                "The column order can still be wrong."
            )
            warnings.append(message)
            result.warnings.append(message)
        if count_meaningful_chars(text) < config.MIN_CHARS_FOR_NONEMPTY_PAGE:
            sparse_pages += 1
        page_texts.append(text)
        result.pages.append(PdfPageContent(
            number=index + 1,
            text=text,
            char_count=count_meaningful_chars(text),
            warnings=warnings,
            column_reordered=reordered,
            image_fraction=page_images[index] if index < len(page_images) else 0.0,
        ))

    full_text = "\n\n".join(t for t in page_texts if t.strip())
    total_chars = count_meaningful_chars(full_text)
    avg_chars = total_chars / max(len(page_texts), 1)
    result.text = full_text

    if total_chars < config.MIN_MEANINGFUL_CHARS or avg_chars < config.MIN_CHARS_PER_PDF_PAGE:
        result.status = STATUS_NEEDS_OCR
        result.warnings.append(_NEEDS_OCR_WARNING)
        return result

    if sparse_pages:
        result.warnings.append(
            f"{sparse_pages} of {len(page_texts)} page(s) contain little or no extractable text and may be "
            "images; OCR (Phase 2) would be needed to read them."
        )
    result.status = PARSE_OK
    return result


def parse_pdf(path: Path) -> ParseResult:
    """Phase 1 PDF parser. Image-only PDFs return ``needs_ocr`` and empty text."""
    read = read_pdf(path)
    text = read.text if read.status == PARSE_OK else ""
    return ParseResult(
        text=text,
        source_format="pdf",
        status=read.status,
        page_count=read.page_count,
        file_name=read.file_name,
        warnings=list(read.warnings),
        errors=list(read.errors),
        links=list(read.links) if read.status == PARSE_OK else [],
    )
