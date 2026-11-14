"""Evaluate skill extraction on manually labelled SYNTHETIC examples.

Usage (from the project folder):
    python evaluation/evaluate_skills.py
    python evaluation/evaluate_skills.py --verbose          # list every false positive / negative
    python evaluation/evaluate_skills.py --json report.json

Important: the examples were written by the same author as the extractor and are
small. The numbers show regressions and known weaknesses; they are NOT an estimate
of accuracy on real-world resumes.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import extract_skills  # noqa: E402

DEFAULT_EXAMPLES = Path(__file__).resolve().parent / "labelled_examples.json"


def prf(tp: int, fp: int, fn: int):
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    if precision is None or recall is None or (precision + recall) == 0:
        f1 = None if (precision is None or recall is None) else 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return precision, recall, f1


def evaluate(examples):
    totals = defaultdict(int)
    by_type = defaultdict(lambda: defaultdict(int))
    errors = []
    ev_correct = ev_total = 0

    for ex in examples:
        predicted = {s.name: s.evidence_type for s in extract_skills(ex["text"])}
        expected = set(ex["expected_skills"])
        expected_used = set(ex.get("expected_used", []))
        pred_names = set(predicted)

        tp, fp, fn = expected & pred_names, pred_names - expected, expected - pred_names
        for bucket in (totals, by_type[ex["type"]]):
            bucket["tp"] += len(tp)
            bucket["fp"] += len(fp)
            bucket["fn"] += len(fn)
            bucket["examples"] += 1
        if fp or fn:
            errors.append({"id": ex["id"], "type": ex["type"], "text": ex["text"],
                           "false_positives": sorted(fp), "false_negatives": sorted(fn)})
        for skill in tp:                      # evidence-type check on correctly found skills
            ev_total += 1
            want = "used" if skill in expected_used else "mentioned"
            ev_correct += predicted[skill] == want

    p, r, f = prf(totals["tp"], totals["fp"], totals["fn"])
    per_type = {}
    for t, c in by_type.items():
        pr, rc, f1 = prf(c["tp"], c["fp"], c["fn"])
        per_type[t] = {"examples": c["examples"], "tp": c["tp"], "fp": c["fp"], "fn": c["fn"],
                       "precision": pr, "recall": rc, "f1": f1}
    return {
        "examples": len(examples), "true_positives": totals["tp"], "false_positives": totals["fp"],
        "false_negatives": totals["fn"], "precision": p, "recall": r, "f1": f,
        "evidence_type_accuracy": (ev_correct / ev_total) if ev_total else None,
        "evidence_type_checked": ev_total, "per_type": per_type, "errors": errors,
    }


def _fmt(x):
    return "n/a" if x is None else f"{x:.3f}"


def print_report(rep, verbose=False):
    print("Skill-extraction evaluation (synthetic, manually labelled examples)")
    print("-" * 66)
    print(f"Examples: {rep['examples']}   TP: {rep['true_positives']}  FP: {rep['false_positives']}  FN: {rep['false_negatives']}")
    print(f"Precision: {_fmt(rep['precision'])}   Recall: {_fmt(rep['recall'])}   F1: {_fmt(rep['f1'])}   (micro-averaged)")
    print(f"Used-vs-mentioned accuracy on correctly detected skills: {_fmt(rep['evidence_type_accuracy'])} "
          f"({rep['evidence_type_checked']} checked)")
    print("\nBy example type:")
    print(f"{'type':<22}{'n':>3}{'TP':>5}{'FP':>5}{'FN':>5}{'P':>8}{'R':>8}{'F1':>8}")
    for t, c in sorted(rep["per_type"].items()):
        print(f"{t:<22}{c['examples']:>3}{c['tp']:>5}{c['fp']:>5}{c['fn']:>5}"
              f"{_fmt(c['precision']):>8}{_fmt(c['recall']):>8}{_fmt(c['f1']):>8}")
    print(f"\nExamples with at least one error: {len(rep['errors'])}")
    if verbose or rep["errors"]:
        for e in rep["errors"]:
            print(f"  [{e['id']}/{e['type']}] FP={e['false_positives']} FN={e['false_negatives']}")
            if verbose:
                print("      " + e["text"].replace("\n", "\n      "))
    print("\nCaveat: small synthetic set written by the extractor's author; not a real-world accuracy estimate.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--examples", default=str(DEFAULT_EXAMPLES), help="Path to labelled examples JSON")
    ap.add_argument("--verbose", action="store_true", help="Show the text of every failing example")
    ap.add_argument("--json", help="Write the full report to this JSON file")
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    with open(args.examples, "r", encoding="utf-8") as fh:
        examples = json.load(fh)
    rep = evaluate(examples)
    print_report(rep, verbose=args.verbose)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nReport written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
