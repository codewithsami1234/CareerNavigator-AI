"""Structured errors for the document-intelligence layer.

Public pipeline functions (``analyze_resume``, ``analyze_document``) catch these
and return a failed ``ResumeAnalysis`` instead of crashing the caller. Lower-level
helpers may raise them when a dependency or a file is unusable.
"""
from __future__ import annotations


class DocumentReadError(Exception):
    """A resume file could not be validated or read."""


class TesseractUnavailable(DocumentReadError):
    """The Tesseract program is missing or the configured path is wrong."""

    error_code = "tesseract_missing"
