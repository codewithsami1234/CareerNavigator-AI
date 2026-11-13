"""Local job-description reading and comparison.

``analyze_job`` and ``compare`` are provided by ``pipeline`` so callers have
one entry point. The pieces here are the parser, the requirement extractor,
and the matcher.
"""
from .matcher import compare_requirements
from .parser import prepare_job
from .requirements import classify_priority, degree_level, extract_requirements

__all__ = [
    "prepare_job",
    "extract_requirements",
    "classify_priority",
    "degree_level",
    "compare_requirements",
]
