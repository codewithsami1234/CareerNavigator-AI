"""Run Tesseract on a preprocessed page image.

``recognize_image`` reads one image. ``ocr_image`` compares a few OpenCV
strategies and keeps the one with more readable text. Confidence is reported
and is never treated as proof that the text is correct.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import config
from errors import DocumentReadError, TesseractUnavailable
from extraction.text_merge import repair_ocr_text
from utils.text_cleaner import count_meaningful_chars

_LANG_RE = re.compile(r"^[A-Za-z0-9_]+(\+[A-Za-z0-9_]+)*$")
_WINDOWS_CANDIDATES = (
    Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
    Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
)


def install_hint() -> str:
    """Actionable install note for a missing Tesseract program."""
    return (
        "Install Tesseract OCR for Windows from https://github.com/UB-Mannheim/tesseract/wiki "
        "and add it to PATH, or set the TESSERACT_CMD environment variable to the executable "
        r'(for example C:\Program Files\Tesseract-OCR\tesseract.exe). '
        "You can also pass --tesseract on the command line. Then run pip install -r requirements.txt "
        "if the pytesseract package is missing."
    )


def locate_tesseract(explicit: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Return ``(path, message)``. An explicit path is not replaced by a guess."""
    if explicit:
        candidate = Path(explicit)
        if candidate.is_file():
            return str(candidate), f"Tesseract found at {candidate}."
        return None, f"Tesseract executable was not found at '{explicit}'. {install_hint()}"

    env_cmd = os.environ.get("TESSERACT_CMD", "").strip() or (config.TESSERACT_CMD or "")
    if env_cmd:
        candidate = Path(env_cmd)
        if candidate.is_file():
            return str(candidate), f"Tesseract found at {candidate}."
        return None, f"TESSERACT_CMD is set to '{env_cmd}', but that file does not exist. {install_hint()}"

    found = shutil.which("tesseract")
    if found:
        return found, f"Tesseract found at {found}."
    for candidate in _WINDOWS_CANDIDATES:
        if candidate.is_file():
            return str(candidate), f"Tesseract found at {candidate}."
    return None, f"Tesseract OCR is not installed. {install_hint()}"


def require_tesseract(explicit: Optional[str] = None) -> str:
    """Return the executable path or raise ``TesseractUnavailable``."""
    path, message = locate_tesseract(explicit)
    if not path:
        raise TesseractUnavailable(message)
    return path


def _validate_lang(lang: str) -> str:
    if not lang or not _LANG_RE.fullmatch(lang) or len(lang) > 64:
        raise DocumentReadError(
            f"OCR language '{lang}' is not a valid Tesseract language code (example: eng)."
        )
    return lang


@dataclass
class OcrSettings:
    """OCR knobs. None means "use config / environment"."""
    tesseract_cmd: Optional[str] = None
    lang: Optional[str] = None
    psm: Optional[int] = None
    oem: Optional[int] = None
    timeout_seconds: Optional[int] = None


@dataclass
class OcrResult:
    text: str = ""
    status: str = "failed"                     # "ok" | "empty" | "failed"
    mean_confidence: Optional[float] = None
    warnings: List[str] = None                  # type: ignore[assignment]
    error: Optional[str] = None
    error_code: Optional[str] = None
    strategy: Optional[str] = None

    def __post_init__(self) -> None:
        if self.warnings is None:
            self.warnings = []


def _text_from_data(data: dict) -> Tuple[str, List[float]]:
    lines: List[str] = []
    words: List[str] = []
    confidences: List[float] = []
    current = None
    texts = data.get("text") or []
    for index, raw in enumerate(texts):
        try:
            confidence = float(data["conf"][index])
        except (TypeError, ValueError, KeyError, IndexError):
            confidence = -1.0
        token = str(raw).strip()
        if confidence < 0 or not token:
            continue
        try:
            key = (data["block_num"][index], data["par_num"][index], data["line_num"][index])
        except (KeyError, IndexError):
            key = (0, 0, index)
        if current is None:
            current = key
        if key != current:
            lines.append(" ".join(words))
            words = []
            current = key
        words.append(token)
        confidences.append(confidence)
    if words:
        lines.append(" ".join(words))
    return "\n".join(lines), confidences


def _mean(values: Sequence[float]) -> Optional[float]:
    if not values:
        return None
    return float(sum(values) / len(values))


def _run_tesseract(image, settings: OcrSettings) -> Tuple[str, List[float]]:
    """Execute Tesseract. Raises ``TesseractUnavailable`` or ``DocumentReadError``."""
    try:
        import pytesseract
    except ImportError as exc:
        raise DocumentReadError(
            "pytesseract is not installed. Run: pip install -r requirements.txt"
        ) from exc

    executable = require_tesseract(settings.tesseract_cmd)
    lang = _validate_lang(settings.lang or config.OCR_LANGUAGE)
    psm = config.OCR_PSM if settings.psm is None else int(settings.psm)
    oem = config.OCR_OEM if settings.oem is None else int(settings.oem)
    timeout = config.OCR_TIMEOUT_SECONDS if settings.timeout_seconds is None else int(settings.timeout_seconds)
    if psm < 0 or psm > 13 or oem < 0 or oem > 3:
        raise DocumentReadError(f"OCR settings are out of range (oem={oem}, psm={psm}).")
    if timeout <= 0:
        raise DocumentReadError("OCR timeout must be a positive number of seconds.")

    pytesseract.pytesseract.tesseract_cmd = executable
    config_arg = f"--oem {oem} --psm {psm}"
    try:
        data = pytesseract.image_to_data(
            image,
            lang=lang,
            config=config_arg,
            output_type=pytesseract.Output.DICT,
            timeout=timeout,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise TesseractUnavailable(f"Tesseract OCR is not installed. {install_hint()}") from exc
    except RuntimeError as exc:
        # pytesseract uses RuntimeError when the process times out or returns an error.
        raise DocumentReadError(f"Tesseract failed: {exc}") from exc
    text, confidences = _text_from_data(data)
    return text, confidences


def recognize_image(image, settings: Optional[OcrSettings] = None) -> OcrResult:
    """OCR one image. An empty page and an engine failure are different statuses."""
    settings = settings or OcrSettings()
    try:
        text, confidences = _run_tesseract(image, settings)
    except TesseractUnavailable as exc:
        return OcrResult(status="failed", error=str(exc), error_code=TesseractUnavailable.error_code)
    except DocumentReadError as exc:
        code = "pytesseract_missing" if "pytesseract" in str(exc) else "tesseract_failed"
        return OcrResult(status="failed", error=str(exc), error_code=code)
    except Exception as exc:
        return OcrResult(
            status="failed",
            error=f"Tesseract failed ({exc.__class__.__name__}): {exc}",
            error_code="tesseract_failed",
        )

    text = repair_ocr_text(text or "")
    mean = _mean(confidences)
    if count_meaningful_chars(text) == 0:
        return OcrResult(
            text="",
            status="empty",
            mean_confidence=mean,
            warnings=[
                "OCR ran but returned no readable text. "
                "Use a clearer, properly oriented photo or scan and try again."
            ],
            error=None,
        )
    warnings: List[str] = []
    if mean is not None and mean < 60:
        warnings.append(
            f"Mean OCR confidence is {mean:.0f}. This estimate is not proof the text is correct."
        )
    return OcrResult(text=text, status="ok", mean_confidence=mean, warnings=warnings)


def _attempt_record(variant, result: OcrResult) -> dict:
    return {
        "strategy": variant.name,
        "readability_score": round(float(variant.score), 3),
        "status": result.status,
        "char_count": count_meaningful_chars(result.text) if result.status != "failed" else 0,
        "mean_confidence": None if result.mean_confidence is None else round(float(result.mean_confidence), 2),
        "error_code": result.error_code,
    }


def _rank(result: OcrResult) -> float:
    if result.status == "failed":
        return -1.0
    chars = count_meaningful_chars(result.text)
    confidence = result.mean_confidence if result.mean_confidence is not None else 0.0
    return chars + max(confidence, 0.0) * 0.3


def ocr_image(image, settings: Optional[OcrSettings] = None) -> Tuple[OcrResult, dict]:
    """Preprocess ``image`` and OCR the best candidates.

    Engine failures are not retried: a missing Tesseract will fail the next
    strategy as well. Empty text is retried on another preprocessing strategy.
    """
    from vision.preprocess import prepare_candidates, select_candidates

    settings = settings or OcrSettings()
    try:
        variants = prepare_candidates(image)
    except ImportError as exc:
        return OcrResult(status="failed", error=str(exc), error_code="opencv_missing"), {"notes": [str(exc)]}
    except Exception as exc:
        return OcrResult(
            status="failed",
            error=f"Image preprocessing failed ({exc.__class__.__name__}): {exc}",
            error_code="preprocess_failed",
        ), {"notes": [str(exc)]}

    selected, notes = select_candidates(variants)
    attempts = []
    best: Optional[OcrResult] = None
    best_rank = -1.0
    for variant in selected[: config.MAX_OCR_STRATEGY_ATTEMPTS]:
        result = recognize_image(variant.image, settings)
        result.strategy = variant.name
        attempts.append(_attempt_record(variant, result))
        if result.status == "failed":
            best = result
            break
        rank = _rank(result)
        if rank > best_rank:
            best_rank = rank
            best = result
        chars = count_meaningful_chars(result.text)
        confidence = result.mean_confidence if result.mean_confidence is not None else -1.0
        if chars >= config.LOW_OCR_CHARS and confidence >= 70:
            notes.append(f"Stopped after '{variant.name}' because the text yield and confidence were adequate.")
            break
    if best is None:
        best = OcrResult(status="failed", error="No preprocessing candidate was produced.", error_code="preprocess_failed")

    winner = next((item for item in variants if item.name == best.strategy), selected[0] if selected else None)
    diagnostics = {
        "winner": best.strategy,
        "estimated_skew_degrees": None if not variants else round(abs(float(variants[0].skew_degrees)), 3),
        "applied_rotation_degrees": None if winner is None else round(float(winner.applied_rotation_degrees), 3),
        "width": None if winner is None else int(winner.width),
        "height": None if winner is None else int(winner.height),
        "steps": [] if winner is None else list(winner.steps),
        "readability_score": None if winner is None else round(float(winner.score), 3),
        "attempts": attempts,
        "notes": notes,
        "candidates": [
            {
                "name": item.name,
                "readability_score": round(float(item.score), 3),
                "steps": list(item.steps),
                "width": int(item.width),
                "height": int(item.height),
            }
            for item in variants
        ],
    }
    return best, diagnostics
