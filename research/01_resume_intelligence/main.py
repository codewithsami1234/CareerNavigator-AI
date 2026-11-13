"""Command-line interface for the Phase 1 resume-intelligence pipeline.

Usage:
    python main.py path\to\resume.pdf
    python main.py path\to\resume.docx --output out\result.json
    python main.py path\to\resume.txt --json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pipeline import analyze_document, analyze_resume
from schemas import ResumeAnalysis, STATUS_PARTIAL, STATUS_SUCCESS


def format_summary(a: ResumeAnalysis, *, phase: str = "Phase 1") -> str:
    out = []
    add = out.append
    add("=" * 64)
    add(f"CareerNavigator AI - Resume Analysis ({phase})")
    add("=" * 64)
    add(f"File:    {a.file_name or '(unknown)'}")
    add(f"Format:  {a.source_format}" + (f"  ({a.page_count} page(s))" if a.page_count else ""))
    add(f"Status:  {a.status.upper()}")
    for err in a.errors:
        add(f"ERROR:   {err}")
    for warn in a.warnings:
        add(f"WARNING: {warn}")
    if a.status not in (STATUS_SUCCESS, STATUS_PARTIAL):
        return "\n".join(out)

    c = a.contact
    add("\n-- Contact --")
    add(f"Name: {c.name or '-'}")
    add(f"Email: {c.email or '-'}   Phone: {c.phone or '-'}")
    add(f"Location: {c.location or '-'}")
    if c.linkedin or c.github:
        add(f"LinkedIn: {c.linkedin or '-'}   GitHub: {c.github or '-'}")
    if c.leetcode or c.twitter:
        add(f"LeetCode: {c.leetcode or '-'}   X: {c.twitter or '-'}")

    add("\n-- Sections detected --")
    add(", ".join(f"{s.name} ({len([l for l in s.content.splitlines() if l.strip()])} lines)"
                  for s in a.sections) or "none")

    add(f"\n-- Skills ({len(a.skills)}) --")
    by_cat = {}
    for s in a.skills:
        by_cat.setdefault(s.category, []).append(s)
    for cat, skills in by_cat.items():
        add(f"{cat}: " + ", ".join(f"{s.name}{'*' if s.evidence_type == 'used' else ''}" for s in skills))
    if a.skills:
        add("(* = evidence of use in Experience/Projects; others are only mentioned)")

    add(f"\n-- Education ({len(a.education)}) --")
    for e in a.education:
        years = f"{e.start_year or '?'}-{e.end_year or ('present' if e.ongoing else '?')}"
        add(f"* {e.degree or '?'} | {e.field_of_study or '-'} | {e.institution or '-'} | {years}")

    add(f"\n-- Experience ({len(a.experience)}) --")
    for x in a.experience:
        add(f"* {x.title or '?'} at {x.organization or '?'} | {x.start_date or '?'} - {x.end_date or '?'}")

    add(f"\n-- Projects ({len(a.projects)}) --")
    for p in a.projects:
        tech = f"  [{', '.join(p.technologies)}]" if p.technologies else ""
        add(f"* {p.name or '(unnamed)'}{tech}")
        for url in p.links:
            add(f"    {url}")

    add(f"\n-- Certifications & courses ({len(a.certifications)}) --")
    for cert in a.certifications:
        extra = " | ".join(str(v) for v in (cert.issuer, cert.year) if v)
        add(f"* [{cert.kind}] {cert.name}" + (f" | {extra}" if extra else ""))

    if a.text_provenance:
        add("\n-- Text sources --")
        for src in a.text_provenance:
            where = f"page {src.page_number}" if src.page_number else "document"
            conf = f", confidence {src.confidence:.0f}" if src.confidence is not None else ""
            note = " (duplicate, not included in the analysis)" if src.suppressed_duplicate else ""
            add(f"{where}: {src.method} ({src.char_count} chars{conf}){note}")
    return "\n".join(out)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Extract structured information from a resume. "
                    "PDF, DOCX and TXT work as in Phase 1. "
                    "--ocr also accepts PNG/JPEG images and scanned or mixed PDFs."
    )
    p.add_argument("path", help="Path to the resume (.pdf, .docx, .txt, or with --ocr a .png/.jpg/.jpeg)")
    p.add_argument("-o", "--output", help="Write the full structured result to this JSON file")
    p.add_argument("--json", action="store_true", help="Print the full JSON to the screen instead of the summary")
    p.add_argument("--taxonomy", help="Path to a custom skills_taxonomy.json")
    p.add_argument("--ocr", action="store_true",
                   help="Use OpenCV and Tesseract when native text is missing (images, scans, mixed PDFs)")
    p.add_argument("--tesseract", help="Path to tesseract.exe (implies --ocr). Overrides TESSERACT_CMD")
    p.add_argument("--ocr-lang", default=None, help="Tesseract language code (default: eng)")
    return p


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):      # avoid UnicodeEncodeError on Windows consoles
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = build_parser().parse_args(argv)
    document_mode = bool(args.ocr or args.tesseract)
    if document_mode:
        analysis = analyze_document(
            args.path,
            taxonomy_path=args.taxonomy,
            ocr=True,
            tesseract_cmd=args.tesseract,
            ocr_lang=args.ocr_lang,
        )
    else:
        analysis = analyze_resume(args.path, taxonomy_path=args.taxonomy)

    if args.output:
        try:
            out_path = Path(args.output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(analysis.to_json(), encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: could not write output file: {exc}", file=sys.stderr)
            return 2

    print(analysis.to_json() if args.json else format_summary(
        analysis, phase="Phase 2" if document_mode else "Phase 1",
    ))
    if args.output:
        print(f"\nJSON written to: {args.output}")
    return 0 if analysis.status in (STATUS_SUCCESS, STATUS_PARTIAL) else 1


if __name__ == "__main__":
    sys.exit(main())
