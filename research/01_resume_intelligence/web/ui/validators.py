"""Upload captions. The pipeline still performs the real validation."""
from __future__ import annotations

import config
from web.service import SUPPORTED_EXTENSIONS


def supported_label() -> str:
    return ", ".join(ext.lstrip(".").upper() for ext in sorted(SUPPORTED_EXTENSIONS))


def resume_limit_caption() -> str:
    return (
        f"Supported files: PDF, DOCX, TXT, PNG, and JPEG. Maximum {config.MAX_FILE_SIZE_MB} MB. "
        "PNG and JPEG are photographed or exported resume images and are read only when OCR is on. "
        "The file is read in a temporary folder and deleted after the pipeline returns. "
        "It is not stored and it is not sent to an external service."
    )
