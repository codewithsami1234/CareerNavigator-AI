"""Layout helpers for PDF text: column order and repeated margins.

These are heuristics. A page is reordered only when word positions show a clear
vertical gap between two text regions. Otherwise the original PyMuPDF line order
is kept. Nothing here decides that a layout is ATS-compatible.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import List, Optional, Sequence

import config

_SPACE_RE = re.compile(r"\s+")


@dataclass
class TextLine:
    y0: float
    y1: float
    x0: float
    x1: float
    text: str


def _norm_key(text: str) -> str:
    return _SPACE_RE.sub(" ", text).strip().lower()


def detect_vertical_gutter(words: Sequence[Sequence], page_width: float) -> Optional[float]:
    """Return an x position that splits two columns, or None.

    ``words`` items are PyMuPDF word tuples ``(x0, y0, x1, y1, text, ...)``.
    A gutter is a near-empty vertical band in the middle of the page with a
    substantial amount of text on both sides. Full-width lines fill that band,
    so the function refuses to guess and the caller keeps the original order.
    """
    if page_width <= 1 or len(words) < 16:
        return None
    bins = 36
    hist = [0] * bins
    for word in words:
        try:
            x0 = float(word[0])
            x1 = float(word[2])
        except (TypeError, IndexError, ValueError):
            continue
        center = (x0 + x1) / 2.0
        if center < 0 or center > page_width:
            continue
        hist[min(bins - 1, int(center / page_width * bins))] += 1
    total = sum(hist)
    if total < 16:
        return None

    # Only near-empty bins count. A bin that holds even one word is text, not a gutter.
    low = int(total * 0.008)
    start = int(bins * 0.28)
    end = int(bins * 0.72)
    best: Optional[tuple] = None
    index = start
    while index < end:
        if hist[index] <= low:
            stop = index
            while stop < end and hist[stop] <= low:
                stop += 1
            width = stop - index
            # A one- or two-bin hole is a normal word space, not a column gutter.
            if width >= 3 and (best is None or width > best[0]):
                best = (width, index, stop)
            index = stop
        else:
            index += 1
    if best is None:
        return None
    _, left_edge, right_edge = best
    left_mass = sum(hist[:left_edge])
    right_mass = sum(hist[right_edge:])
    if left_mass < total * 0.18 or right_mass < total * 0.18:
        return None
    return ((left_edge + right_edge) / 2.0) / bins * page_width


def order_lines_for_columns(lines: Sequence[TextLine], gutter_x: float, page_width: float) -> List[TextLine]:
    """Read the left column of each band before the right column.

    Lines that cross the gutter stay in vertical order and separate the bands,
    so a full-width heading is not pushed into one column.
    """
    ordered: List[TextLine] = []
    band: List[TextLine] = []

    def flush() -> None:
        if not band:
            return
        left: List[TextLine] = []
        right: List[TextLine] = []
        for line in band:
            center = (line.x0 + line.x1) / 2.0
            if center <= gutter_x:
                left.append(line)
            else:
                right.append(line)
        left.sort(key=lambda item: (item.y0, item.x0))
        right.sort(key=lambda item: (item.y0, item.x0))
        ordered.extend(left)
        ordered.extend(right)
        band.clear()

    for line in sorted(lines, key=lambda item: (item.y0, item.x0)):
        crosses = line.x0 < gutter_x - 12 and line.x1 > gutter_x + 12
        wide = (line.x1 - line.x0) >= page_width * 0.65
        if crosses or wide:
            flush()
            ordered.append(line)
        else:
            band.append(line)
    flush()
    return ordered


def _in_margin(line: TextLine, height: float) -> bool:
    if height <= 0:
        return False
    top = line.y1 <= height * config.PDF_MARGIN_TOP_RATIO
    bottom = line.y0 >= height * config.PDF_MARGIN_BOTTOM_RATIO
    return top or bottom


def strip_repeated_margin_lines(pages: List[List[TextLine]], heights: Sequence[float]) -> int:
    """Drop repeated header/footer lines from every page after the first.

    A line qualifies only when it sits in the top or bottom margin, is short,
    does not contain an email address, and repeats on enough pages. The first
    page keeps the line so a repeated name is not discarded entirely.
    Returns the number of removed lines. No-op for documents shorter than
    ``PDF_HEADER_MIN_PAGES``.
    """
    count = len(pages)
    if count < config.PDF_HEADER_MIN_PAGES or len(heights) != count:
        return 0
    seen_counts: Counter = Counter()
    for lines, height in zip(pages, heights):
        keys = set()
        for line in lines:
            if not _in_margin(line, height):
                continue
            stripped = line.text.strip()
            if not stripped or len(stripped) > config.PDF_MARGIN_LINE_MAX_CHARS or "@" in stripped:
                continue
            keys.add(_norm_key(stripped))
        for key in keys:
            seen_counts[key] += 1

    needed = max(config.PDF_HEADER_MIN_PAGES, int(count * 0.6))
    repeated = {key for key, hits in seen_counts.items() if hits >= needed}
    if not repeated:
        return 0

    removed = 0
    for index, (lines, height) in enumerate(zip(pages, heights)):
        if index == 0:
            continue
        kept: List[TextLine] = []
        for line in lines:
            key = _norm_key(line.text)
            if key in repeated and _in_margin(line, height):
                removed += 1
                continue
            kept.append(line)
        pages[index] = kept
    return removed


def join_lines(lines: Sequence[TextLine]) -> str:
    """Join lines, inserting a blank line at a clear vertical gap or a new column."""
    output: List[str] = []
    prev_bottom: Optional[float] = None
    prev_top: Optional[float] = None
    for line in lines:
        text = line.text.strip()
        if not text:
            continue
        if prev_bottom is not None and prev_top is not None:
            jumped_up = line.y0 + 2 < prev_top
            height = max(line.y1 - line.y0, 1.0)
            gap = (line.y0 - prev_bottom) > config.PDF_PARAGRAPH_GAP_RATIO * height
            if jumped_up or gap:
                output.append("")
        output.append(text)
        prev_bottom = line.y1
        prev_top = line.y0
    return "\n".join(output)
