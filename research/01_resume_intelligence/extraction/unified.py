"""One extraction path for text files, native PDFs, scans and resume images.

Flow: validate -> native text when it is sufficient -> OpenCV and Tesseract
for sparse or image pages -> one text string -> the Phase 1 analysers.

``analyze_resume`` does not call this module, so Phase 1 behaviour stays the
same. ``analyze_document`` does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import config
from extraction.text_merge import (
    TextPiece, combine_native_and_ocr, included_text, mark_duplicate_pages, tokens,
)
from parsers.docx_parser import parse_docx
from parsers.pdf_parser import PdfPageContent, read_pdf
from parsers.text_parser import parse_text_file
from schemas import (
    PARSE_OK, STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, DocumentLink, QualityFinding, QualityReport,
    TextProvenance,
)
from utils.text_cleaner import count_meaningful_chars, has_meaningful_text
from vision.quality import assess_image, build_report


@dataclass
class PageRecord:
    page_number: Optional[int]
    method: str
    text: str
    confidence: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    suppressed_duplicate: bool = False
    preprocess: Optional[dict] = None


@dataclass
class DocumentExtraction:
    text: str = ""
    source_format: str = "unknown"
    status: str = STATUS_FAILED
    file_name: Optional[str] = None
    page_count: Optional[int] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    pages: List[PageRecord] = field(default_factory=list)
    quality: Optional[QualityReport] = None
    links: List[DocumentLink] = field(default_factory=list)


def page_needs_ocr(char_count: int, image_fraction: float) -> bool:
    """True when native text is missing, short, or only a caption on a large image."""
    if char_count >= 400:
        return False
    if char_count >= config.NATIVE_PAGE_SUFFICIENT_CHARS and image_fraction < 0.35:
        return False
    if char_count < config.NATIVE_PAGE_SUFFICIENT_CHARS:
        return True
    return image_fraction >= 0.35


def _validate(path: Union[str, Path]) -> Tuple[Optional[Path], List[str]]:
    try:
        candidate = Path(path)
    except TypeError:
        return None, ["The file path is not valid."]
    if not candidate.exists():
        return None, [f"File not found: {candidate.name or candidate}"]
    if not candidate.is_file():
        return None, [f"Not a file: {candidate.name or candidate}"]
    extension = candidate.suffix.lower()
    if extension not in config.PHASE2_EXTENSIONS:
        supported = ", ".join(sorted(config.PHASE2_EXTENSIONS))
        return None, [f"Unsupported file type '{extension or '(none)'}'. Supported types: {supported}."]
    try:
        size = candidate.stat().st_size
    except OSError as exc:
        return None, [f"Could not read file information: {exc.__class__.__name__}"]
    if size == 0:
        return None, ["The file is empty (0 bytes)."]
    if size > config.MAX_FILE_SIZE_BYTES:
        return None, [config.file_too_large_message(size)]
    return candidate, []


def ocr_bgr_image(image, settings, page_number: Optional[int] = None):
    """OCR one BGR page. Tests patch this function to avoid a Tesseract binary."""
    from ocr.tesseract_ocr import ocr_image

    result, diagnostics = ocr_image(image, settings)
    diagnostics["page_number"] = page_number
    return result, diagnostics


def _render_pdf_pages(path: Path, numbers: List[int]) -> Tuple[Dict[int, object], Dict[int, str]]:
    import numpy as np

    try:
        import cv2
    except ImportError:
        return {}, {number: "OpenCV is not installed. Run: pip install -r requirements.txt" for number in numbers}
    try:
        import pymupdf
    except ImportError:
        return {}, {number: "PyMuPDF is not installed. Run: pip install -r requirements.txt" for number in numbers}

    images: Dict[int, object] = {}
    errors: Dict[int, str] = {}
    try:
        doc = pymupdf.open(str(path))
    except Exception as exc:
        message = f"Could not render PDF pages ({exc.__class__.__name__})."
        return {}, {number: message for number in numbers}
    try:
        for number in numbers:
            index = number - 1
            if index < 0 or index >= doc.page_count:
                errors[number] = f"Page {number} is outside the PDF."
                continue
            try:
                pix = doc[index].get_pixmap(dpi=config.PDF_RENDER_DPI, alpha=False, colorspace=pymupdf.csRGB)
                array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n).copy()
                if pix.n == 4:
                    image = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
                elif pix.n == 1:
                    image = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
                else:
                    image = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
            except Exception as exc:
                errors[number] = f"Page {number} could not be rendered ({exc.__class__.__name__})."
                continue
            if image.shape[0] * image.shape[1] > config.MAX_IMAGE_PIXELS:
                errors[number] = (
                    f"Page {number} rendered to {image.shape[1]}x{image.shape[0]}, "
                    f"over the {config.MAX_IMAGE_PIXELS} pixel limit."
                )
                continue
            images[number] = image
    finally:
        try:
            doc.close()
        except Exception:
            pass
    return images, errors


def _observation(page_number, method, text, confidence, findings, measured, preprocess) -> dict:
    return {
        "page_number": page_number,
        "method": method,
        "char_count": count_meaningful_chars(text),
        "confidence": confidence,
        "findings": findings,
        "measured": measured,
        "preprocess": preprocess,
    }


def _attach_quality(document: DocumentExtraction, observations: List[dict], used_ocr: bool) -> None:
    report = build_report(observations, used_ocr=used_ocr)
    document.quality = report
    for finding in report.findings:
        if finding.severity == "warning":
            document.warnings.append(f"[{finding.kind}] {finding.message}")


def _from_native_parser(parsed, method: str, source_format: str) -> DocumentExtraction:
    document = DocumentExtraction(
        source_format=source_format,
        file_name=parsed.file_name,
        page_count=parsed.page_count,
        warnings=list(parsed.warnings),
        errors=list(parsed.errors),
        status=parsed.status,
    )
    if parsed.status == STATUS_FAILED:
        _attach_quality(document, [], used_ocr=False)
        return document
    text = parsed.text or ""
    if not has_meaningful_text(text):
        document.status = STATUS_EMPTY
        if not any("meaningful" in warning.lower() for warning in document.warnings):
            document.warnings.append("The document was read successfully but contains no meaningful text.")
        _attach_quality(document, [_observation(None, method, "", None, [], {}, None)], used_ocr=False)
        return document
    document.text = text
    document.status = PARSE_OK
    document.links = list(getattr(parsed, "links", []) or [])
    document.pages.append(PageRecord(page_number=None, method=method, text=text, confidence=None))
    _attach_quality(
        document,
        [_observation(None, method, text, None, [], {}, None)],
        used_ocr=False,
    )
    return document


def _pieces_to_records(page_number: Optional[int], pieces: List[TextPiece], warnings: List[str],
                       preprocess: Optional[dict]) -> List[PageRecord]:
    records = []
    for index, piece in enumerate(pieces):
        records.append(PageRecord(
            page_number=page_number,
            method=piece.method,
            text=piece.text,
            confidence=piece.confidence,
            warnings=list(warnings) if index == 0 else [],
            suppressed_duplicate=piece.suppressed_duplicate,
            preprocess=preprocess if index == 0 else None,
        ))
    return records


def _ocr_page_image(image, settings, page_number: int, native_text: str) -> Tuple[List[PageRecord], List[str], List[str], dict, bool]:
    """Return records, warnings, errors, observation, and whether OCR ran successfully enough to count."""
    warnings: List[str] = []
    errors: List[str] = []
    try:
        result, diagnostics = ocr_bgr_image(image, settings, page_number=page_number)
    except Exception as exc:
        errors.append(f"Page {page_number} OCR failed ({exc.__class__.__name__}): {exc}")
        pieces = combine_native_and_ocr(native_text, "")
        return _pieces_to_records(page_number, pieces, warnings, None), warnings, errors, {}, False

    skew = diagnostics.get("estimated_skew_degrees") or 0.0
    findings = []
    measured = {}
    try:
        findings = assess_image(
            image,
            skew_degrees=float(skew or 0.0),
            page_number=page_number,
            ocr_chars=None if result.status == "failed" else count_meaningful_chars(result.text),
        )
        from vision.quality import measure_image
        measured = measure_image(image)
        measured["skew_degrees"] = float(skew or 0.0)
    except Exception as exc:
        warnings.append(f"Page {page_number} image diagnostics failed ({exc.__class__.__name__}).")

    if result.status == "failed":
        errors.append(result.error or f"Page {page_number} OCR failed.")
        pieces = combine_native_and_ocr(native_text, "")
        ran = False
    elif result.status == "empty":
        warnings.append(f"Page {page_number}: OCR ran but returned no readable text.")
        warnings.extend(result.warnings)
        pieces = combine_native_and_ocr(native_text, "")
        ran = True
    else:
        warnings.extend(f"Page {page_number}: {item}" for item in result.warnings)
        pieces = combine_native_and_ocr(native_text, result.text, ocr_confidence=result.mean_confidence)
        if any(piece.suppressed_duplicate for piece in pieces):
            warnings.append(
                f"Page {page_number}: native text and OCR overlapped, so the duplicate copy was left out."
            )
        native_tokens = tokens(native_text)
        ocr_tokens = tokens(result.text)
        if len(native_tokens) >= 8 and len(ocr_tokens) >= 8:
            union = native_tokens | ocr_tokens
            overlap = len(native_tokens & ocr_tokens) / len(union) if union else 1.0
            if overlap < 0.3:
                findings.append(QualityFinding(
                    code="extraction_inconsistency",
                    kind="heuristic",
                    severity="warning",
                    message=(
                        f"Page {page_number} native text and OCR text disagree "
                        f"(token overlap {overlap:.2f}). One of the two readings may be incomplete."
                    ),
                    evidence={"page": page_number, "token_overlap": round(overlap, 3)},
                ))
        ran = True

    records = _pieces_to_records(page_number, pieces, warnings, diagnostics)
    if not records and native_text.strip():
        records = [PageRecord(page_number=page_number, method=config.METHOD_NATIVE_PDF, text=native_text)]
    observation = _observation(
        page_number,
        config.METHOD_OCR if ran or result.status == "failed" else config.METHOD_NATIVE_PDF,
        included_text(pieces) if pieces else native_text,
        result.mean_confidence,
        findings,
        measured,
        diagnostics,
    )
    return records, warnings, errors, observation, ran


def _from_pdf(path: Path, ocr: bool, settings) -> DocumentExtraction:
    read = read_pdf(path)
    document = DocumentExtraction(
        source_format="pdf",
        file_name=read.file_name,
        page_count=read.page_count,
        warnings=list(read.warnings),
        errors=list(read.errors),
        status=read.status,
    )
    if read.status == STATUS_FAILED:
        _attach_quality(document, [], used_ocr=False)
        return document
    document.links = list(read.links)

    ocr_pages: List[PdfPageContent] = []
    for page in read.pages:
        if page_needs_ocr(page.char_count, page.image_fraction):
            ocr_pages.append(page)

    observations = []
    page_blobs: List[Tuple[int, str, List[PageRecord]]] = []

    for page in read.pages:
        if page not in ocr_pages:
            record = PageRecord(
                page_number=page.number,
                method=config.METHOD_NATIVE_PDF,
                text=page.text,
                warnings=list(page.warnings),
            )
            page_blobs.append((page.number, page.text, [record]))
            observations.append(_observation(
                page.number, config.METHOD_NATIVE_PDF, page.text, None,
                [QualityFinding(
                    code="possible_multicolumn",
                    kind="heuristic",
                    severity="warning",
                    message=(
                        f"Page {page.number} may use more than one column. Reading order was estimated "
                        "from geometry and can still be wrong."
                    ),
                    evidence={"page": page.number},
                )] if page.column_reordered else [],
                {},
                None,
            ))

    used_ocr = False
    if ocr_pages and not ocr:
        document.warnings.append(
            f"OCR is turned off, so {len(ocr_pages)} page(s) with little or no native text were not read."
        )
        for page in ocr_pages:
            if page.text.strip():
                record = PageRecord(page_number=page.number, method=config.METHOD_NATIVE_PDF, text=page.text)
                page_blobs.append((page.number, page.text, [record]))
            observations.append(_observation(page.number, config.METHOD_NATIVE_PDF, page.text, None, [], {}, None))
    elif ocr_pages:
        images, render_errors = _render_pdf_pages(path, [page.number for page in ocr_pages])
        for page in ocr_pages:
            if page.number in render_errors:
                document.errors.append(render_errors[page.number])
                if page.text.strip():
                    record = PageRecord(page_number=page.number, method=config.METHOD_NATIVE_PDF, text=page.text)
                    page_blobs.append((page.number, page.text, [record]))
                observations.append(_observation(page.number, config.METHOD_NATIVE_PDF, page.text, None, [], {}, None))
                continue
            records, warnings, errors, observation, ran = _ocr_page_image(
                images[page.number], settings, page.number, page.text,
            )
            document.warnings.extend(warnings)
            document.errors.extend(errors)
            used_ocr = used_ocr or ran
            blob = included_text([
                TextPiece(record.text, record.method, record.suppressed_duplicate, record.confidence)
                for record in records
            ])
            page_blobs.append((page.number, blob, records))
            if observation:
                observations.append(observation)

    page_blobs.sort(key=lambda item: item[0])
    duplicate_numbers = set(mark_duplicate_pages([(number, text) for number, text, _records in page_blobs]))
    ordered_text = []
    for number, text, records in page_blobs:
        if number in duplicate_numbers:
            document.warnings.append(
                f"Page {number} repeats the previous page and was left out of the combined text."
            )
            for record in records:
                record.suppressed_duplicate = True
                document.pages.append(record)
            continue
        if text.strip():
            ordered_text.append(text.strip())
        document.pages.extend(records)

    document.text = "\n\n".join(ordered_text)
    if used_ocr and has_meaningful_text(document.text):
        document.warnings.append(
            "OCR confidence is a Tesseract estimate, not a guarantee that the extracted text is correct."
        )
    _attach_quality(document, observations, used_ocr=used_ocr)
    _set_pdf_status(document, ocr_requested=bool(ocr_pages) and ocr, had_ocr_pages=bool(ocr_pages))
    _apply_ocr_readability(document, observations, used_ocr=used_ocr)
    # Those sentences belong to the Phase 1 parser, which never calls OCR.
    # This path already decided to keep native text, run OCR, or report why it
    # could not, so the "will be added later" wording would be wrong here.
    document.warnings = [
        warning for warning in document.warnings
        if "No resume data was extracted" not in warning and "would be needed" not in warning
    ]
    return document


def _ocr_measurements(observations: List[dict]) -> tuple:
    """Lowest OCR confidence and the busiest ink ratio among OCR pages."""
    confidences = []
    inks = []
    for observation in observations:
        if observation.get("method") != config.METHOD_OCR:
            continue
        confidence = observation.get("confidence")
        if confidence is not None:
            confidences.append(float(confidence))
        measured = observation.get("measured") or {}
        if measured.get("ink_ratio") is not None:
            inks.append(float(measured["ink_ratio"]))
    confidence = min(confidences) if confidences else None
    measured = {"ink_ratio": max(inks)} if inks else {}
    return confidence, measured


def _discard_unreadable_text(document: DocumentExtraction, reason: str) -> None:
    """Drop OCR characters that are not reliable enough to analyze."""
    document.status = STATUS_FAILED
    document.errors.append(reason)
    document.text = ""
    for record in document.pages:
        if record.method == config.METHOD_OCR:
            record.text = ""


def _apply_ocr_readability(document: DocumentExtraction, observations: List[dict], *, used_ocr: bool) -> None:
    from ocr.readability import BLANK_IMAGE_MESSAGE, unreliable_ocr_reason

    if not used_ocr:
        return
    if has_meaningful_text(document.text):
        confidence, measured = _ocr_measurements(observations)
        reason = unreliable_ocr_reason(document.text, confidence, measured)
        if reason:
            _discard_unreadable_text(document, reason)
        return
    if document.status == STATUS_EMPTY and not document.errors:
        document.errors.append(BLANK_IMAGE_MESSAGE)


def _set_pdf_status(document: DocumentExtraction, *, ocr_requested: bool, had_ocr_pages: bool) -> None:
    if has_meaningful_text(document.text):
        document.status = PARSE_OK
        return
    if document.errors and (ocr_requested or not had_ocr_pages):
        document.status = STATUS_FAILED
        return
    if had_ocr_pages and not ocr_requested:
        document.status = STATUS_NEEDS_OCR
        return
    if any(record.method == config.METHOD_OCR for record in document.pages):
        document.status = STATUS_EMPTY
        return
    if document.errors:
        document.status = STATUS_FAILED
        return
    document.status = STATUS_EMPTY


def _from_image(path: Path, ocr: bool, settings) -> DocumentExtraction:
    from vision.image_io import load_image

    document = DocumentExtraction(source_format="image", file_name=path.name, page_count=1)
    loaded = load_image(path)
    for warning in loaded.warnings:
        if "resolution is low" in warning.lower():
            continue
        document.warnings.append(warning)
    if not loaded.ok:
        document.status = STATUS_FAILED
        document.errors.extend(loaded.errors)
        _attach_quality(document, [], used_ocr=False)
        return document
    if not ocr:
        document.status = STATUS_NEEDS_OCR
        document.warnings.append(
            "This file is a resume image. OCR is turned off, so no text was read. "
            "Turn on OCR and analyze again. Local Tesseract reads the image."
        )
        _attach_quality(document, [_observation(1, "image", "", None, [], {
            "width_px": loaded.width, "height_px": loaded.height,
        }, None)], used_ocr=False)
        return document

    records, warnings, errors, observation, ran = _ocr_page_image(loaded.image, settings, 1, "")
    document.warnings.extend(warnings)
    document.errors.extend(errors)
    document.pages.extend(records)
    document.text = "\n\n".join(
        record.text.strip() for record in records if record.text.strip() and not record.suppressed_duplicate
    )
    if ran and has_meaningful_text(document.text):
        document.warnings.append(
            "OCR confidence is a Tesseract estimate, not a guarantee that the extracted text is correct."
        )
    if observation:
        _attach_quality(document, [observation], used_ocr=ran)
    else:
        _attach_quality(document, [], used_ocr=ran)
    if has_meaningful_text(document.text):
        document.status = PARSE_OK
    elif document.errors:
        document.status = STATUS_FAILED
    else:
        document.status = STATUS_EMPTY
    _apply_ocr_readability(document, [observation] if observation else [], used_ocr=ran)
    return document


def extract_document(path: Union[str, Path], *, ocr: bool = True, settings=None) -> DocumentExtraction:
    """Validate ``path`` and return native and/or OCR text with provenance.

    Does not raise for bad files or a missing Tesseract. Those become
    ``status``, ``errors`` and ``warnings``.
    """
    from ocr.tesseract_ocr import OcrSettings

    candidate, errors = _validate(path)
    if candidate is None:
        name = None
        try:
            name = Path(str(path)).name if path is not None else None
        except TypeError:
            name = None
        document = DocumentExtraction(status=STATUS_FAILED, file_name=name, errors=errors)
        _attach_quality(document, [], used_ocr=False)
        return document

    settings = settings or OcrSettings()
    extension = candidate.suffix.lower()
    try:
        if extension == ".pdf":
            return _from_pdf(candidate, ocr=ocr, settings=settings)
        if extension == ".docx":
            return _from_native_parser(parse_docx(candidate), config.METHOD_NATIVE_DOCX, "docx")
        if extension == ".txt":
            return _from_native_parser(parse_text_file(candidate), config.METHOD_NATIVE_TEXT, "text")
        return _from_image(candidate, ocr=ocr, settings=settings)
    except Exception as exc:
        return DocumentExtraction(
            status=STATUS_FAILED,
            file_name=candidate.name,
            source_format=extension.lstrip(".") or "unknown",
            errors=[f"Unexpected error while reading the file: {exc.__class__.__name__}: {exc}"],
        )


def provenance_of(document: DocumentExtraction) -> List[TextProvenance]:
    return [
        TextProvenance(
            page_number=record.page_number,
            method=record.method,
            char_count=count_meaningful_chars(record.text),
            confidence=None if record.confidence is None else float(record.confidence),
            suppressed_duplicate=record.suppressed_duplicate,
        )
        for record in document.pages
    ]
