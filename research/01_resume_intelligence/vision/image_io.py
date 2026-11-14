"""Load and validate PNG and JPEG resume images.

Decoding uses ``cv2.imdecode`` so Windows paths with non-ASCII characters work.
The checks are limits, not a judgment of whether the resume is well designed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import config

_PNG = b"\x89PNG\r\n\x1a\n"
_JPEG = b"\xff\xd8\xff"


@dataclass
class LoadedImage:
    image: Optional[object] = None          # BGR ndarray when ok
    width: int = 0
    height: int = 0
    color_mode: str = "unknown"
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.image is not None and not self.errors


def sniff_image_format(data: bytes) -> Optional[str]:
    """Return ``png`` or ``jpeg`` from magic bytes, or None."""
    if data.startswith(_PNG):
        return "png"
    if data.startswith(_JPEG):
        return "jpeg"
    return None


def _expected_format(suffix: str) -> Optional[str]:
    if suffix == ".png":
        return "png"
    if suffix in {".jpg", ".jpeg"}:
        return "jpeg"
    return None


def load_image(path: Path) -> LoadedImage:
    """Read one resume image. Failures are returned on the result, not raised."""
    result = LoadedImage()
    try:
        size = path.stat().st_size
    except OSError as exc:
        result.errors.append(f"Could not read file information: {exc.__class__.__name__}")
        return result
    if size == 0:
        result.errors.append("The file is empty (0 bytes).")
        return result
    if size > config.MAX_FILE_SIZE_BYTES:
        result.errors.append(config.file_too_large_message(size))
        return result
    try:
        data = path.read_bytes()
    except OSError as exc:
        result.errors.append(f"Could not read file: {exc.__class__.__name__}: {exc}")
        return result

    found = sniff_image_format(data)
    expected = _expected_format(path.suffix.lower())
    if found is None:
        result.errors.append(
            "The file is not a valid PNG or JPEG image (the contents do not match the extension)."
        )
        return result
    if expected and found != expected:
        result.errors.append(
            f"The file extension says {expected}, but the contents are {found}."
        )
        return result

    try:
        import cv2
        import numpy as np
    except ImportError:
        result.errors.append("OpenCV is not installed. Run: pip install -r requirements.txt")
        return result

    buffer = np.frombuffer(data, dtype=np.uint8)
    decoded = cv2.imdecode(buffer.copy(), cv2.IMREAD_COLOR)
    if decoded is None or decoded.size == 0:
        result.errors.append("The image could not be decoded. It may be truncated or corrupt.")
        return result

    height, width = int(decoded.shape[0]), int(decoded.shape[1])
    result.width = width
    result.height = height
    result.color_mode = "bgr"
    if width < config.MIN_IMAGE_SIDE_PX or height < config.MIN_IMAGE_SIDE_PX:
        result.errors.append(
            f"Image is too small ({width}x{height}). "
            f"Each side must be at least {config.MIN_IMAGE_SIDE_PX} pixels."
        )
        return result
    if width > config.MAX_IMAGE_SIDE_PX or height > config.MAX_IMAGE_SIDE_PX:
        result.errors.append(
            f"Image is too large ({width}x{height}). "
            f"Each side must be at most {config.MAX_IMAGE_SIDE_PX} pixels."
        )
        return result
    if width * height > config.MAX_IMAGE_PIXELS:
        result.errors.append(
            f"Image has too many pixels ({width * height}). The limit is {config.MAX_IMAGE_PIXELS}."
        )
        return result
    if min(width, height) < config.LOW_RESOLUTION_MIN_SIDE:
        result.warnings.append(
            f"Image resolution is low ({width}x{height}). OCR may miss small text."
        )
    result.image = decoded
    return result
