"""DOCX text extraction with python-docx (paragraphs, tables, headers, footers, text boxes).

Text boxes are read in document order. A floating box whose anchor is stored
clearly below its paragraph is emitted after that paragraph's own text, and a
negative offset is emitted before it. Inline boxes stay beside the runs that
contain them.

This is not a full layout engine. Page-relative positions, overlapping shapes,
and text boxes that share a table cell with other text can still differ from
the visual page. When Word stores a modern drawing and a VML fallback for the
same shape, the fallback is omitted once the drawing already has text.
"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional

from schemas import DocumentLink, ParseResult, PARSE_OK

_PAGE_NUMBER_RE = re.compile(r"^(?:page\s*)?\d{1,3}(?:\s*(?:of|/)\s*\d{1,3})?$", re.IGNORECASE)
# 0.2 inch, about one text line. Smaller offsets stay in XML run order.
_ANCHOR_BELOW_EMU = 182880
_MAX_BLOCK_DEPTH = 8
_RUN_TEXT_TAGS = {"t", "tab", "br", "cr", "noBreakHyphen", "ptab"}

_TEXTBOX_WARNING = (
    "The DOCX contains text boxes. Their text was included using document order and "
    "stored anchor positions; complex floating layouts can still differ from the visual page."
)


def _is_page_number(line: str) -> bool:
    return bool(_PAGE_NUMBER_RE.match(line.strip()))


def _local(element) -> str:
    tag = getattr(element, "tag", None)
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _ancestor(element, name: str):
    node = element.getparent()
    while node is not None:
        if _local(node) == name:
            return node
        node = node.getparent()
    return None


def _descendants(element, name: str):
    """Descendants with this local tag. Avoids prefixed XPath on raw drawing nodes."""
    return [node for node in element.iter() if node is not element and _local(node) == name]


def _outer_text_boxes(paragraph):
    """Text boxes that belong to this paragraph, not to a nested text box or a deletion."""
    boxes = []
    for txbx in _descendants(paragraph, "txbxContent"):
        if _ancestor(txbx, "txbxContent") is not None:
            continue
        if _ancestor(txbx, "del") is not None:
            continue
        boxes.append(txbx)
    return boxes


def _textbox_plain(txbx) -> str:
    parts = []
    for node in _descendants(txbx, "t"):
        if node.text:
            parts.append(node.text)
    return " ".join(parts).strip()


def _is_fallback_duplicate(txbx) -> bool:
    """True when this box is the VML fallback of a drawing that already has text."""
    fallback = _ancestor(txbx, "Fallback")
    if fallback is None:
        return False
    alternate = fallback.getparent()
    if alternate is None:
        return False
    for sibling in alternate.iterchildren():
        if sibling is fallback or _local(sibling) != "Choice":
            continue
        choice_boxes = [
            box for box in _descendants(sibling, "txbxContent") if _ancestor(box, "Fallback") is None
        ]
        if not choice_boxes:
            continue
        if any(_textbox_plain(box) for box in choice_boxes):
            return True
        return False
    return False


def _paragraph_relative_offset(txbx) -> Optional[int]:
    """Vertical offset in EMUs relative to the anchor paragraph.

    ``None`` means the box is inline, or its position is page-relative and is
    not converted into a page coordinate.
    """
    node = txbx.getparent()
    anchor = None
    while node is not None:
        name = _local(node)
        if name == "inline":
            return None
        if name == "anchor":
            anchor = node
            break
        if name == "txbxContent":
            return None
        node = node.getparent()
    if anchor is None:
        return None
    for pos in anchor.iterchildren():
        if _local(pos) != "positionV":
            continue
        if pos.get("relativeFrom") != "paragraph":
            return None
        for child in pos.iterchildren():
            name = _local(child)
            if name == "posOffset" and child.text and child.text.strip():
                try:
                    return int(child.text.strip())
                except ValueError:
                    return None
            if name == "align" and child.text:
                align = child.text.strip().lower()
                if align in {"bottom", "outside"}:
                    return _ANCHOR_BELOW_EMU
                if align in {"top", "center", "inside"}:
                    return 0
        return None
    return None


def _paragraph_text(paragraph) -> str:
    """Paragraph text, including a raw drawing paragraph that is not a ``CT_P``."""
    if type(paragraph).__name__ == "CT_P":
        return paragraph.text or ""
    parts = []
    for child in paragraph.iterchildren():
        name = _local(child)
        if name == "r":
            parts.append(_run_text(child))
        elif name == "hyperlink":
            parts.append("".join(
                _run_text(run) for run in child.iterchildren() if _local(run) == "r"
            ))
    return "".join(parts)


def _run_text(run) -> str:
    if type(run).__name__ == "CT_R":
        return run.text or ""
    parts = []
    for child in run.iterchildren():
        name = _local(child)
        if name == "t":
            parts.append(child.text or "")
        elif name in {"tab", "ptab"}:
            parts.append("\t")
        elif name in {"cr", "br"}:
            if name == "br":
                br_type = child.get(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type"
                )
                if br_type not in (None, "textWrapping"):
                    continue
            parts.append("\n")
        elif name == "noBreakHyphen":
            parts.append("-")
    return "".join(parts)


def _run_child_text(child) -> str:
    name = _local(child)
    if name not in _RUN_TEXT_TAGS:
        return ""
    return str(child)


def _textbox_lines(txbx, document, notes: Dict[str, bool], depth: int) -> List[str]:
    from docx.table import Table

    lines: List[str] = []
    for child in txbx.iterchildren():
        name = _local(child)
        if name == "p":
            lines.extend(_paragraph_lines(child, document, notes, depth + 1))
        elif name == "tbl":
            lines.extend(_table_lines(Table(child, document), document, notes, depth + 1))
    return [line for line in lines if line.strip()]


def _emit_text_boxes(boxes, document, notes, depth) -> List[str]:
    lines: List[str] = []
    for box in boxes:
        lines.extend(_textbox_lines(box, document, notes, depth))
    return lines


def _flush_text(buf: List[str], lines: List[str]) -> None:
    if not buf:
        return
    chunk = "".join(buf)
    buf.clear()
    if chunk:
        lines.append(chunk)


def _consume_inline_run(run, pending: set, document, notes, depth, buf, lines) -> None:
    boxes = [box for box in _descendants(run, "txbxContent") if id(box) in pending]
    if not boxes:
        buf.append(_run_text(run))
        return
    for child in run.iterchildren():
        if _local(child) in _RUN_TEXT_TAGS:
            buf.append(_run_child_text(child))
            continue
        found = [box for box in _descendants(child, "txbxContent") if id(box) in pending]
        if _local(child) == "txbxContent" and id(child) in pending:
            found.append(child)
        if not found:
            continue
        _flush_text(buf, lines)
        for box in found:
            if id(box) not in pending:
                continue
            pending.remove(id(box))
            lines.extend(_textbox_lines(box, document, notes, depth))


def _interleave_inline(paragraph, inline_boxes, document, notes, depth) -> List[str]:
    pending = {id(box) for box in inline_boxes}
    lines: List[str] = []
    buf: List[str] = []
    for child in paragraph.iterchildren():
        name = _local(child)
        if name not in {"r", "hyperlink"}:
            continue
        if name == "hyperlink" and not any(
            id(box) in pending for box in _descendants(child, "txbxContent")
        ):
            if type(child).__name__ == "CT_Hyperlink":
                buf.append(child.text or "")
            else:
                buf.append("".join(
                    _run_text(run) for run in child.iterchildren() if _local(run) == "r"
                ))
            continue
        if name == "hyperlink":
            for run in child.iterchildren():
                if _local(run) == "r":
                    _consume_inline_run(run, pending, document, notes, depth, buf, lines)
            continue
        _consume_inline_run(child, pending, document, notes, depth, buf, lines)
    _flush_text(buf, lines)
    for box in inline_boxes:
        if id(box) not in pending:
            continue
        pending.remove(id(box))
        lines.extend(_textbox_lines(box, document, notes, depth))
    return lines


def _paragraph_lines(paragraph, document, notes: Dict[str, bool], depth: int = 0) -> List[str]:
    """One body or text-box paragraph, including text boxes owned by that paragraph."""
    if depth > _MAX_BLOCK_DEPTH:
        return [_paragraph_text(paragraph)]
    if _descendants(paragraph, "txbxContent"):
        notes["text_boxes"] = True

    before = []
    after = []
    inline = []
    for box in _outer_text_boxes(paragraph):
        if _is_fallback_duplicate(box):
            continue
        offset = _paragraph_relative_offset(box)
        if offset is not None and offset >= _ANCHOR_BELOW_EMU:
            after.append(box)
        elif offset is not None and offset < 0:
            before.append(box)
        else:
            inline.append(box)

    lines: List[str] = []
    lines.extend(_emit_text_boxes(before, document, notes, depth))
    if inline:
        lines.extend(_interleave_inline(paragraph, inline, document, notes, depth))
    else:
        own = _paragraph_text(paragraph)
        if own.strip() or not (before or after):
            lines.append(own)
    lines.extend(_emit_text_boxes(after, document, notes, depth))
    return lines


def _cell_text(cell, document, notes: Dict[str, bool], depth: int) -> str:
    parts = []
    for paragraph in cell.paragraphs:
        for line in _paragraph_lines(paragraph._element, document, notes, depth + 1):
            if line.strip():
                parts.append(line.strip())
    return " ".join(parts)


def _table_lines(table, document, notes: Dict[str, bool], depth: int = 0) -> List[str]:
    lines = []
    for row in table.rows:
        cells = []
        for cell in row.cells:
            txt = _cell_text(cell, document, notes, depth)
            if txt and (not cells or cells[-1] != txt):  # merged cells repeat their text
                cells.append(txt)
        if cells:
            lines.append(" | ".join(cells))
    return lines


def _container_lines(container, document, notes: Dict[str, bool]) -> List[str]:
    """Paragraphs and tables from a header or footer.

    Paragraphs are still emitted before tables, matching the previous header
    and footer order.
    """
    lines: List[str] = []
    for paragraph in container.paragraphs:
        for line in _paragraph_lines(paragraph._element, document, notes):
            if line.strip():
                lines.append(line)
    for table in container.tables:
        lines.extend(_table_lines(table, document, notes))
    return lines


_REL_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _body_hyperlinks(document) -> List[DocumentLink]:
    """External hyperlinks in the body, with their visible text."""
    links: List[DocumentLink] = []
    try:
        rels = document.part.rels
    except Exception:
        return links
    for node in document.element.body.iter():
        if _local(node) != "hyperlink":
            continue
        rid = node.get(_REL_ID)
        rel = rels.get(rid) if rid else None
        if rel is None or not getattr(rel, "is_external", False):
            continue
        uri = (rel.target_ref or "").strip()
        if not uri.lower().startswith(("http://", "https://")):
            continue
        anchor = " ".join("".join(t.text or "" for t in _descendants(node, "t")).split())
        links.append(DocumentLink(text=anchor, uri=uri))
    return links


def parse_docx(path: Path) -> ParseResult:
    result = ParseResult(source_format="docx", file_name=path.name)
    try:
        import docx
        from docx.table import Table
    except ImportError:
        result.status = "failed"
        result.errors.append("python-docx is not installed. Run: pip install -r requirements.txt")
        return result

    try:
        document = docx.Document(str(path))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        result.status = "failed"
        result.errors.append(
            f"Could not open DOCX (file is corrupted or not a real .docx): {exc.__class__.__name__}"
        )
        return result
    except Exception as exc:  # python-docx raises PackageNotFoundError etc.
        result.status = "failed"
        result.errors.append(
            f"Could not open DOCX (file is corrupted or not a real .docx): {exc.__class__.__name__}"
        )
        return result

    body: List[str] = []
    notes: Dict[str, bool] = {"text_boxes": False}
    try:
        for child in document.element.body.iterchildren():
            tag = _local(child)
            if tag == "p":
                body.extend(_paragraph_lines(child, document, notes))
            elif tag == "tbl":
                body.extend(_table_lines(Table(child, document), document, notes))

        header_lines: List[str] = []
        footer_lines: List[str] = []
        for section in document.sections:
            header_lines.extend(_container_lines(section.header, document, notes))
            footer_lines.extend(_container_lines(section.footer, document, notes))
    except Exception as exc:
        result.status = "failed"
        result.errors.append(f"Could not read DOCX content: {exc.__class__.__name__}: {exc}")
        return result

    # Drop a header line only when the body already contains the same text.
    body_present = {line.strip() for line in body if line.strip()}
    header_kept = [line for line in header_lines if line.strip() and line.strip() not in body_present]
    footer_kept = [line for line in footer_lines if line.strip() and not _is_page_number(line)]
    if footer_kept:
        result.warnings.append("Footer text other than a page number was included.")
    if notes["text_boxes"]:
        result.warnings.append(_TEXTBOX_WARNING)
    lines = header_kept + body + footer_kept

    result.text = "\n".join(lines)
    result.links = _body_hyperlinks(document)
    result.status = PARSE_OK
    return result
