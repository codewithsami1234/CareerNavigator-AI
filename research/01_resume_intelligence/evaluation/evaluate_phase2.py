"""Fixture-based evaluation for Phase 2 document extraction.

Usage (from the resume-intelligence folder):
    python evaluation/evaluate_phase2.py
    python evaluation/evaluate_phase2.py --json outputs/phase2_eval.json

This is a regression check on synthetic files, not a real-world OCR or
skill-extraction accuracy study. Skill numbers come from the existing
50-snippet set. OCR token overlap is reported only when Tesseract is
installed, and only for a page this script renders itself.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))

import evaluate_skills  # noqa: E402
from ocr.tesseract_ocr import locate_tesseract  # noqa: E402
from pipeline import analyze_document, analyze_resume  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"

_LIMITATIONS = [
    "Skill precision, recall and F1 are computed on 50 synthetic snippets written with the extractor. They are not an estimate of accuracy on real resumes.",
    "Document rates below count the bundled synthetic fixtures only. They are not a field study.",
    "OCR token overlap, when present, is measured on one page rendered by this script from known text. It is not a real-world OCR accuracy figure.",
    "Expected and unexpected counts compare each synthetic file with the status this script already named. They are not a field failure rate.",
    "No model was trained in this phase. OpenCV preprocessing is heuristic. Tesseract, if installed, uses its own pretrained OCR models, which this project does not train or modify.",
    "Processing time and tracemalloc peak are for this machine and this run. They will differ on another computer.",
]


def _skill_summary():
    examples = json.loads(evaluate_skills.DEFAULT_EXAMPLES.read_text(encoding="utf-8"))
    report = evaluate_skills.evaluate(examples)
    return {
        "examples": report["examples"],
        "true_positives": report["true_positives"],
        "false_positives": report["false_positives"],
        "false_negatives": report["false_negatives"],
        "precision": report["precision"],
        "recall": report["recall"],
        "f1": report["f1"],
        "evidence_type_accuracy": report["evidence_type_accuracy"],
        "examples_with_errors": len(report["errors"]),
    }


def _timed(func):
    started_here = not tracemalloc.is_tracing()
    if started_here:
        tracemalloc.start()
    started = time.perf_counter()
    try:
        value = func()
    finally:
        elapsed = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        if started_here:
            tracemalloc.stop()
    return value, elapsed, peak


def _case(name, path: Path, route: str, expected: str):
    def run():
        if route == "phase1":
            return analyze_resume(path)
        return analyze_document(path)

    analysis, elapsed, peak = _timed(run)
    return {
        "name": name,
        "route": route,
        "status": analysis.status,
        "expected_status": expected,
        "matches_expected": analysis.status == expected,
        "seconds": round(elapsed, 4),
        "peak_memory_bytes": peak,
        "text_length": analysis.text_length,
        "skill_count": len(analysis.skills),
        "error_count": len(analysis.errors),
        "warning_count": len(analysis.warnings),
    }


def _robustness_specs(tmp: Path):
    """Small synthetic files whose expected statuses are already known."""
    blank = tmp / "blank.txt"
    blank.write_text(" \n\n\t\n", encoding="utf-8")
    tiny = tmp / "tiny.txt"
    tiny.write_text("hello\n", encoding="utf-8")
    other = tmp / "notes.rtf"
    other.write_text("{\\rtf1 not a resume}", encoding="utf-8")
    return (
        (blank.name, blank, "phase1", "empty"),
        (tiny.name, tiny, "phase1", "empty"),
        (other.name, other, "phase1", "failed"),
    )


def _ocr_fixture(tmp: Path):
    path, message = locate_tesseract(None)
    if not path:
        return {
            "ran": False,
            "reason": message,
            "token_recall": None,
        }
    import pymupdf

    # The previous three lines were 42 letters/digits. analyze_text discards
    # text below MIN_MEANINGFUL_CHARS (50) before sections or skills exist,
    # which reported status "empty" and token recall 0 even after OCR ran.
    lines = (
        "Alex Morgan",
        "alex.morgan@example.com",
        "Skills",
        "Python Django Docker SQL Flask",
        "Experience",
        "Built services with Python and Docker",
    )
    expected = ["python", "django", "docker", "sql", "flask", "alex"]
    image = tmp / "ocr_fixture.png"
    doc = pymupdf.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        page.insert_text((72, 90 + index * 40), line, fontsize=20, fontname="helv")
    pix = page.get_pixmap(dpi=220, alpha=False)
    pix.save(str(image))
    doc.close()
    analysis, elapsed, peak = _timed(lambda: analyze_document(image, tesseract_cmd=path))
    # The analysis does not keep the raw string. Re-read through sections + contact.
    blob = " ".join(section.content for section in analysis.sections).lower()
    if analysis.contact.email:
        blob += " " + analysis.contact.email.lower()
    if analysis.contact.name:
        blob += " " + analysis.contact.name.lower()
    blob += " " + " ".join(skill.name.lower() for skill in analysis.skills)
    found = [token for token in expected if token in blob]
    return {
        "ran": True,
        "tesseract": path,
        "status": analysis.status,
        "seconds": round(elapsed, 4),
        "peak_memory_bytes": peak,
        "expected_tokens": expected,
        "found_tokens": found,
        "token_recall": round(len(found) / len(expected), 3),
        "limitation": "Synthetic rendered page only. Token recall here is not a general OCR benchmark.",
    }


def evaluate():
    readable = [
        ("sample_resume_full.pdf", "phase1", "success"),
        ("sample_resume_full.docx", "phase1", "success"),
        ("sample_resume_full.txt", "phase1", "success"),
    ]
    expected_other = [
        ("image_only_scan_like.pdf", "phase1", "needs_ocr"),
        ("malformed.pdf", "phase1", "failed"),
        ("malformed.docx", "phase1", "failed"),
        ("encrypted.pdf", "phase1", "failed"),
    ]
    # Load parsers and the skill taxonomy before timing so the first file is not
    # charged for one-time imports.
    analyze_resume(FIXTURES / "sample_resume_full.txt")
    documents = []
    for name, route, expected in readable + expected_other:
        documents.append(_case(name, FIXTURES / name, route, expected))
    documents.append(_case("sample_resume_full.pdf", FIXTURES / "sample_resume_full.pdf", "phase2", "success"))

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for name, path, route, expected in _robustness_specs(tmp_path):
            documents.append(_case(name, path, route, expected))
        ocr = _ocr_fixture(tmp_path)

    by_name = {(item["name"], item["route"]): item for item in documents}
    readable_ok = sum(
        1 for name, route, expected in readable if by_name[(name, route)]["status"] == expected
    )
    other_ok = sum(
        1 for name, route, expected in expected_other if by_name[(name, route)]["status"] == expected
    )
    phase2_native = by_name[("sample_resume_full.pdf", "phase2")]
    unexpected = [
        {"name": item["name"], "route": item["route"], "expected_status": item["expected_status"], "status": item["status"]}
        for item in documents if not item["matches_expected"]
    ]
    if ocr["ran"] and ocr["status"] not in {"success", "partial"}:
        unexpected.append({"name": "ocr_fixture.png", "route": "phase2", "expected_status": "success or partial", "status": ocr["status"]})

    attempted = len(documents)
    successes = sum(1 for item in documents if item["status"] in {"success", "partial"})
    empties = sum(1 for item in documents if item["status"] == "empty")
    failures = sum(1 for item in documents if item["status"] == "failed")
    timed_seconds = [item["seconds"] for item in documents]
    if ocr.get("seconds") is not None:
        timed_seconds.append(ocr["seconds"])
    checked = attempted + (1 if ocr["ran"] else 0)
    return {
        "phase1_skill_evaluation": _skill_summary(),
        "documents": documents,
        "summary": {
            "documents_timed": attempted,
            "status_success_or_partial": successes,
            "status_empty": empties,
            "status_failed": failures,
            "document_processing_success_rate": readable_ok / len(readable),
            "readable_fixture_success_rate": readable_ok / len(readable),
            "expected_non_success_match_rate": other_ok / len(expected_other),
            "expected_outcome_count": checked - len(unexpected),
            "unexpected_outcome_count": len(unexpected),
            "unexpected_outcomes": unexpected,
            "processing_time_seconds": round(sum(timed_seconds), 4),
            "slowest_document_seconds": round(max(timed_seconds), 4) if timed_seconds else None,
            "phase2_native_pdf_status": phase2_native["status"],
            "ocr_fixture_ran": ocr["ran"],
            "ocr_token_recall": ocr.get("token_recall"),
            "synthetic_only": True,
        },
        "ocr_fixture": ocr,
        "limitations": list(_LIMITATIONS),
    }


def _fmt(value):
    return "n/a" if value is None else f"{value:.3f}"


def print_report(report):
    skill = report["phase1_skill_evaluation"]
    summary = report["summary"]
    print("Phase 2 fixture evaluation (synthetic documents)")
    print("-" * 66)
    print(f"Skill snippets: {skill['examples']}  P {_fmt(skill['precision'])}  "
          f"R {_fmt(skill['recall'])}  F1 {_fmt(skill['f1'])}")
    print(f"Document processing success rate (readable fixtures): {_fmt(summary['document_processing_success_rate'])}")
    print(f"Expected failed/needs_ocr match rate: {_fmt(summary['expected_non_success_match_rate'])}")
    print(f"Expected outcomes: {summary['expected_outcome_count']}  "
          f"unexpected: {summary['unexpected_outcome_count']}")
    print(f"Phase 2 native PDF status: {summary['phase2_native_pdf_status']}")
    peaks = [item["peak_memory_bytes"] for item in report["documents"]]
    print(f"Timed documents: {summary['documents_timed']}  "
          f"success/partial {summary['status_success_or_partial']}  "
          f"empty {summary['status_empty']}  failed {summary['status_failed']}")
    print(f"Processing time: {summary['processing_time_seconds']:.3f}s total, "
          f"slowest {summary['slowest_document_seconds']:.3f}s")
    if peaks:
        print(f"Peak traced memory across timed documents: {max(peaks) / (1024 * 1024):.2f} MB "
              "(tracemalloc, this process)")
    if summary["unexpected_outcomes"]:
        print("Unexpected:")
        for item in summary["unexpected_outcomes"]:
            print(f"  {item['name']} ({item['route']}): expected {item['expected_status']}, got {item['status']}")
    print("\nPer document:")
    print(f"{'name':<32}{'route':<8}{'status':<12}{'expected':<12}{'sec':>8}{'skills':>8}")
    for item in report["documents"]:
        print(f"{item['name']:<32}{item['route']:<8}{item['status']:<12}{item['expected_status']:<12}"
              f"{item['seconds']:>8.3f}{item['skill_count']:>8}")
    ocr = report["ocr_fixture"]
    print("\nOCR fixture:")
    if not ocr["ran"]:
        print("  not run:", ocr["reason"])
    else:
        print(f"  status {ocr['status']}  token recall {_fmt(ocr['token_recall'])}  "
              f"found {ocr['found_tokens']}")
    print("\nLimitations:")
    for line in report["limitations"]:
        print(" -", line)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", help="Write the report to this JSON file")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    report = evaluate()
    print_report(report)
    if args.json:
        destination = Path(args.json)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nReport written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
