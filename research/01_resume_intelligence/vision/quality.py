"""Resume readability diagnostics.

Findings are split into measured properties, heuristic warnings and assessments
this phase does not make (including ATS compatibility). A warning is a reason
to look at the page, not a verdict that the resume is unreadable.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import config
from schemas import QualityFinding, QualityReport

_LIMITATIONS = [
    "OpenCV measurements and layout rules are heuristics. They do not understand resume wording or design intent.",
    "Tesseract confidence, when present, is an engine estimate. It is not proof that the text is correct.",
    "ATS compatibility is not assessed from image processing or from these warnings.",
    "Multi-column reading order is only a geometric guess. It can still be wrong.",
]


def measure_image(image) -> Dict[str, float]:
    """Measure a BGR or gray page. Values are plain Python floats."""
    import numpy as np

    from vision.preprocess import to_gray

    gray = to_gray(image)
    height, width = gray.shape[:2]
    return {
        "width_px": float(width),
        "height_px": float(height),
        "contrast_std": float(gray.std()),
        "ink_ratio": float(np.mean(gray < 180)),
        "mean_brightness": float(gray.mean()),
        "white_row_fraction": float(np.mean(np.mean(gray < 180, axis=1) < 0.02)),
    }


def findings_from_measurements(
    measured: Dict[str, Any],
    *,
    page_number: Optional[int] = None,
    ocr_chars: Optional[int] = None,
    multicolumn: bool = False,
) -> List[QualityFinding]:
    """Turn one page's measurements into findings. Missing keys are skipped."""
    findings: List[QualityFinding] = []
    label = f"Page {page_number}" if page_number else "Image"
    width = measured.get("width_px")
    height = measured.get("height_px")
    if width and height:
        width_i, height_i = int(width), int(height)
        findings.append(QualityFinding(
            code="page_dimensions",
            kind="measured",
            severity="info",
            message=f"{label} is {width_i}x{height_i} pixels.",
            evidence={"page": page_number, "width_px": width_i, "height_px": height_i},
        ))
        short_side = min(width_i, height_i)
        long_side = max(width_i, height_i)
        aspect = short_side / long_side if long_side else 1.0
        if short_side < config.LOW_RESOLUTION_MIN_SIDE:
            findings.append(QualityFinding(
                code="low_resolution",
                kind="heuristic",
                severity="warning",
                message=(
                    f"{label} is low resolution ({width_i}x{height_i}). "
                    "Small text may not survive OCR. This is not a final readability judgment."
                ),
                evidence={"page": page_number, "min_side_px": short_side},
            ))
        if aspect < config.UNUSUAL_ASPECT_MIN or aspect > config.UNUSUAL_ASPECT_MAX:
            findings.append(QualityFinding(
                code="unusual_dimensions",
                kind="heuristic",
                severity="warning",
                message=(
                    f"{label} has an unusual aspect ratio ({width_i}x{height_i}). "
                    "It may not be a standard portrait or landscape page."
                ),
                evidence={"page": page_number, "aspect_min_over_max": round(aspect, 3)},
            ))

    if "contrast_std" in measured:
        std = float(measured["contrast_std"])
        findings.append(QualityFinding(
            code="contrast",
            kind="measured",
            severity="info",
            message=f"{label} grayscale standard deviation is {std:.1f}.",
            evidence={"page": page_number, "contrast_std": round(std, 2)},
        ))
        if std < config.LOW_CONTRAST_STD:
            findings.append(QualityFinding(
                code="poor_contrast",
                kind="heuristic",
                severity="warning",
                message=(
                    f"{label} has low contrast (standard deviation {std:.1f}). "
                    "The scan may be faint. This threshold is a heuristic."
                ),
                evidence={"page": page_number, "contrast_std": round(std, 2)},
            ))

    if measured.get("skew_degrees") is not None:
        skew = abs(float(measured["skew_degrees"]))
        findings.append(QualityFinding(
            code="skew_angle",
            kind="measured",
            severity="info",
            message=f"{label} estimated skew is {skew:.1f} degrees.",
            evidence={"page": page_number, "skew_degrees": round(skew, 2)},
        ))
        if skew >= config.EXCESSIVE_SKEW_DEGREES:
            findings.append(QualityFinding(
                code="excessive_skew",
                kind="heuristic",
                severity="warning",
                message=(
                    f"{label} looks skewed by about {skew:.1f} degrees. "
                    "Deskew is attempted when it improves the image, but the angle is an estimate."
                ),
                evidence={"page": page_number, "skew_degrees": round(skew, 2)},
            ))

    ink = measured.get("ink_ratio")
    mean = measured.get("mean_brightness")
    if ink is not None and mean is not None:
        ink_f, mean_f = float(ink), float(mean)
        std = float(measured.get("contrast_std") or 0.0)
        if ink_f <= config.BLANK_INK_RATIO and std < 12:
            findings.append(QualityFinding(
                code="blank_page",
                kind="heuristic",
                severity="warning",
                message=f"{label} looks blank or nearly blank. OCR may return nothing.",
                evidence={"page": page_number, "ink_ratio": round(ink_f, 4), "mean_brightness": round(mean_f, 1)},
            ))
        elif mean_f < 15 and std < 12:
            findings.append(QualityFinding(
                code="solid_dark_page",
                kind="heuristic",
                severity="warning",
                message=f"{label} looks solid dark, so text is unlikely to be readable.",
                evidence={"page": page_number, "mean_brightness": round(mean_f, 1)},
            ))
        white_rows = float(measured.get("white_row_fraction") or 0.0)
        crowded = ink_f >= config.CROWDED_INK_RATIO or (white_rows < 0.08 and ink_f > 0.22)
        if crowded:
            findings.append(QualityFinding(
                code="crowded_layout",
                kind="heuristic",
                severity="warning",
                message=(
                    f"{label} has little whitespace (ink ratio {ink_f:.2f}). "
                    "The page may be crowded or contain overlapping marks. This is not a layout parse."
                ),
                evidence={"page": page_number, "ink_ratio": round(ink_f, 3), "white_row_fraction": round(white_rows, 3)},
            ))

    if multicolumn:
        findings.append(QualityFinding(
            code="possible_multicolumn",
            kind="heuristic",
            severity="warning",
            message=(
                f"{label} may use more than one column. Reading order was estimated from geometry "
                "and can still be wrong."
            ),
            evidence={"page": page_number},
        ))

    if ocr_chars is not None and ocr_chars < config.LOW_OCR_CHARS:
        findings.append(QualityFinding(
            code="low_ocr_yield",
            kind="heuristic",
            severity="warning",
            message=(
                f"{label} OCR produced only {ocr_chars} letter or digit characters. "
                "The page may be empty, faint, or poorly recognised. A low yield is not proof of the cause."
            ),
            evidence={"page": page_number, "ocr_char_count": int(ocr_chars)},
        ))
    return findings


def assess_image(image, *, skew_degrees: float = 0.0, page_number: Optional[int] = None,
                 ocr_chars: Optional[int] = None, multicolumn: bool = False) -> List[QualityFinding]:
    """Measure ``image`` and return findings. ``skew_degrees`` comes from the skew estimator."""
    measured = measure_image(image)
    measured["skew_degrees"] = float(skew_degrees)
    return findings_from_measurements(
        measured, page_number=page_number, ocr_chars=ocr_chars, multicolumn=multicolumn,
    )


def build_report(observations: List[Dict[str, Any]], *, used_ocr: bool) -> QualityReport:
    """Combine per-page observations into one report.

    Each observation may include ``findings`` (already built) plus a plain
    ``measured`` dict and an optional ``preprocess`` dict.
    """
    findings: List[QualityFinding] = []
    pages: List[Dict[str, Any]] = []
    preprocessing: List[Dict[str, Any]] = []
    for obs in observations:
        findings.extend(obs.get("findings") or [])
        measured = dict(obs.get("measured") or {})
        if not measured.get("width_px"):
            findings.append(QualityFinding(
                code="image_quality_not_measured",
                kind="unsupported",
                severity="info",
                message=(
                    f"Page {obs.get('page_number') or '?'} used {obs.get('method', 'native text')}. "
                    "Pixel contrast, resolution and skew were not measured because the page was not rendered."
                ),
                evidence={"page": obs.get("page_number"), "method": obs.get("method")},
            ))
        page_record = {
            "page_number": obs.get("page_number"),
            "method": obs.get("method"),
            "char_count": obs.get("char_count"),
            "confidence": obs.get("confidence"),
        }
        page_record.update(measured)
        pages.append(page_record)
        if obs.get("preprocess"):
            preprocessing.append(obs["preprocess"])

    findings.append(QualityFinding(
        code="ats_compatibility",
        kind="unsupported",
        severity="info",
        message=(
            "ATS compatibility is not assessed. These checks do not label a resume as "
            "ATS-compatible or ATS-incompatible."
        ),
        evidence={},
    ))
    if used_ocr:
        findings.append(QualityFinding(
            code="ocr_confidence_not_guarantee",
            kind="unsupported",
            severity="info",
            message="OCR confidence is a Tesseract estimate, not a guarantee that the extracted text is correct.",
            evidence={},
        ))
    return QualityReport(
        findings=findings,
        measured={"page_count": len(observations), "pages": pages, "preprocessing": preprocessing},
        limitations=list(_LIMITATIONS),
    )
