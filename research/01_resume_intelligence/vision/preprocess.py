"""OpenCV preprocessing for OCR.

Several small strategies are scored with a readability heuristic (contrast,
sharpness, ink coverage). Thresholding is kept only when that score does not
fall well below the grayscale image. This score is not an accuracy measure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import config


@dataclass
class ProcessedImage:
    name: str
    image: object
    steps: List[str]
    score: float
    width: int
    height: int
    skew_degrees: float = 0.0
    applied_rotation_degrees: float = 0.0
    warnings: List[str] = field(default_factory=list)


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise ImportError("OpenCV is not installed. Run: pip install -r requirements.txt") from exc
    return cv2


def to_gray(image) -> object:
    """Return a uint8 grayscale image from a BGR, BGRA or gray array."""
    import numpy as np

    cv2 = _cv2()
    if image is None:
        raise ValueError("No image was provided.")
    if image.ndim == 2:
        gray = image
    elif image.shape[2] == 4:
        gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    else:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if gray.dtype != np.uint8:
        gray = np.clip(gray, 0, 255).astype(np.uint8)
    return gray


def readability_score(gray) -> float:
    """Higher is more likely to be readable. Heuristic only."""
    import numpy as np

    cv2 = _cv2()
    if gray.size == 0:
        return 0.0
    std = float(gray.std())
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    ink = float(np.mean(gray < 180))
    if ink <= 0.004 or ink >= 0.85:
        ink_term = -40.0
    else:
        ink_term = 40.0 * (1.0 - min(abs(ink - 0.12) / 0.12, 1.5))
    return std * 0.35 + min(sharpness, 800.0) / 20.0 + ink_term


def _rotate(image, angle: float, border: int, expand: bool, interpolation: int):
    cv2 = _cv2()
    height, width = image.shape[:2]
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    if expand:
        cos = abs(float(matrix[0, 0]))
        sin = abs(float(matrix[0, 1]))
        new_w = max(1, int(height * sin + width * cos))
        new_h = max(1, int(height * cos + width * sin))
        matrix[0, 2] += new_w / 2.0 - center[0]
        matrix[1, 2] += new_h / 2.0 - center[1]
        size = (new_w, new_h)
    else:
        size = (width, height)
    return cv2.warpAffine(image, matrix, size, flags=interpolation, borderValue=border)


def _projection_score(binary_inv, angle: float) -> float:
    cv2 = _cv2()
    rotated = binary_inv if abs(angle) < 1e-6 else _rotate(
        binary_inv, angle, border=0, expand=False, interpolation=cv2.INTER_NEAREST,
    )
    projection = rotated.sum(axis=1, dtype="float64")
    if projection.size == 0:
        return 0.0
    return float(projection.var())


def estimate_skew(gray) -> Tuple[float, float]:
    """Return ``(applied_rotation, reported_skew)`` in degrees.

    ``reported_skew`` is the tilt estimate (absolute value is what diagnostics
    show). ``applied_rotation`` is the angle passed to warpAffine, or 0 when
    rotating would not help or the tilt is smaller than the correction gate.
    """
    import numpy as np

    cv2 = _cv2()
    if gray.size == 0:
        return 0.0, 0.0
    height, width = gray.shape[:2]
    scale = 720.0 / max(width, 1)
    if scale < 1:
        small = cv2.resize(
            gray,
            (max(1, int(width * scale)), max(1, int(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    else:
        small = gray
    if min(small.shape[:2]) < 20:
        return 0.0, 0.0
    blur = cv2.GaussianBlur(small, (3, 3), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    if int(np.count_nonzero(binary)) < 40:
        return 0.0, 0.0

    zero = _projection_score(binary, 0.0)
    best_angle = 0.0
    best_score = zero
    angle = -config.SKEW_SEARCH_DEGREES
    while angle <= config.SKEW_SEARCH_DEGREES + 1e-6:
        value = _projection_score(binary, angle)
        if value > best_score:
            best_score = value
            best_angle = float(angle)
        angle += config.SKEW_SEARCH_STEP
    if best_score <= zero * 1.01:
        return 0.0, 0.0
    reported = float(best_angle)
    if abs(reported) < config.SKEW_CORRECT_MIN_DEGREES:
        return 0.0, reported
    return reported, reported


def resize_for_ocr(gray):
    """Resize for OCR while keeping the aspect ratio. Returns (image, step name)."""
    cv2 = _cv2()
    height, width = gray.shape[:2]
    if width <= 0 or height <= 0:
        return gray, "resize_skipped"
    scale = 1.0
    pixels = height * width
    if pixels > config.MAX_IMAGE_PIXELS:
        scale = (config.MAX_IMAGE_PIXELS / pixels) ** 0.5
    if width * scale > config.OCR_MAX_WIDTH:
        scale = min(scale, config.OCR_MAX_WIDTH / width)
    elif width < config.OCR_TARGET_MIN_WIDTH and scale == 1.0:
        scale = min(config.OCR_TARGET_MIN_WIDTH / width, config.OCR_MAX_UPSCALE)
    if abs(scale - 1.0) < 0.05:
        return gray, "resize_skipped"
    new_w = max(1, int(round(width * scale)))
    new_h = max(1, int(round(height * scale)))
    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
    return cv2.resize(gray, (new_w, new_h), interpolation=interpolation), f"resize_{width}x{height}_to_{new_w}x{new_h}"


def _light_background(binary):
    """Tesseract expects dark text on a light background."""
    cv2 = _cv2()
    if float(binary.mean()) < 127:
        return cv2.bitwise_not(binary)
    return binary


def _denoise_clahe(gray):
    cv2 = _cv2()
    denoised = cv2.medianBlur(gray, 3)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(denoised)


def _otsu(gray):
    cv2 = _cv2()
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return _light_background(binary)


def _adaptive(gray):
    cv2 = _cv2()
    if min(gray.shape[:2]) < 32:
        return None
    try:
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11,
        )
    except cv2.error:
        return None
    return _light_background(binary)


def _pack(name: str, image, steps: List[str], skew: float, applied: float, warnings: List[str]) -> ProcessedImage:
    return ProcessedImage(
        name=name,
        image=image,
        steps=list(steps),
        score=float(readability_score(image)),
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        skew_degrees=float(skew),
        applied_rotation_degrees=float(applied),
        warnings=list(warnings),
    )


def prepare_candidates(image) -> List[ProcessedImage]:
    """Build a small set of preprocessed images from a BGR or gray page."""
    cv2 = _cv2()
    gray = to_gray(image)
    applied, reported = estimate_skew(gray)
    warnings: List[str] = []
    sources: List[Tuple[str, object, float, List[str]]] = []

    resized, resize_step = resize_for_ocr(gray)
    sources.append(("grayscale", resized, 0.0, ["grayscale", resize_step]))

    if abs(applied) >= config.SKEW_CORRECT_MIN_DEGREES:
        corrected = _rotate(gray, applied, border=255, expand=True, interpolation=cv2.INTER_LINEAR)
        # Keep the rotation only when the leveled image is at least as readable.
        if readability_score(corrected) + 1e-6 >= readability_score(gray) * 0.95:
            deskewed, deskew_resize = resize_for_ocr(corrected)
            sources.append((
                "deskew_grayscale", deskewed, applied,
                ["grayscale", f"deskew_{applied:.1f}deg", deskew_resize],
            ))
        else:
            applied = 0.0
            warnings.append(
                "A skew estimate was not applied because the rotated image looked less readable."
            )

    variants: List[ProcessedImage] = []
    for name, source, rotation, steps in sources:
        variants.append(_pack(name, source, steps, reported, rotation, warnings))
        enhanced = _denoise_clahe(source)
        variants.append(_pack(
            name.replace("grayscale", "denoise_clahe") if "grayscale" in name else name + "_denoise_clahe",
            enhanced,
            steps + ["median_denoise", "clahe"],
            reported,
            rotation,
            warnings,
        ))
        # Thresholds are only added for the unrotated branch. The selector drops
        # them when they score worse than grayscale.
        if rotation == 0.0:
            variants.append(_pack("otsu", _otsu(enhanced), steps + ["median_denoise", "clahe", "otsu"], reported, 0.0, warnings))
            adaptive = _adaptive(enhanced)
            if adaptive is not None:
                variants.append(_pack(
                    "adaptive", adaptive, steps + ["median_denoise", "clahe", "adaptive_threshold"],
                    reported, 0.0, warnings,
                ))
    return variants


def select_candidates(variants: List[ProcessedImage]) -> Tuple[List[ProcessedImage], List[str]]:
    """Order candidates by the readability heuristic and drop harmful ones.

    The grayscale (or deskewed grayscale) score is the reference. A candidate
    more than 15% below that reference is not sent to OCR.
    """
    if not variants:
        return [], ["No preprocessed image could be built."]
    reference_pool = [item for item in variants if item.name in {"grayscale", "deskew_grayscale", "denoise_clahe", "deskew_denoise_clahe"}]
    if not reference_pool:
        reference_pool = list(variants)
    reference = max(item.score for item in reference_pool)
    notes: List[str] = []
    kept: List[ProcessedImage] = []
    for item in sorted(variants, key=lambda candidate: candidate.score, reverse=True):
        if item.score + 1e-6 < reference * 0.85:
            continue
        kept.append(item)
    if not kept:
        kept = [max(variants, key=lambda candidate: candidate.score)]
    winner = kept[0]
    threshold_attempted = any(item.name in {"otsu", "adaptive"} for item in variants)
    threshold_kept = any(item.name in {"otsu", "adaptive"} for item in kept)
    if threshold_attempted and not threshold_kept:
        notes.append(
            "Thresholding scored lower than the grayscale image, so the grayscale version was kept."
        )
    if winner.name != "grayscale" and any(item.name == "grayscale" for item in variants):
        notes.append(f"Readability heuristic preferred '{winner.name}' over plain grayscale.")
    return kept, notes
