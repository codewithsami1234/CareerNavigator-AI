"""The Phase 2 evaluation script runs on the bundled synthetic fixtures."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation"))

import evaluate_phase2  # noqa: E402


def test_phase2_evaluation_reports_fixture_limits():
    report = evaluate_phase2.evaluate()
    summary = report["summary"]
    skill = report["phase1_skill_evaluation"]
    assert skill["examples"] == 50
    assert 0 <= skill["f1"] <= 1
    assert summary["readable_fixture_success_rate"] == 1
    assert summary["document_processing_success_rate"] == 1
    assert summary["expected_non_success_match_rate"] == 1
    assert summary["unexpected_outcome_count"] == 0
    assert summary["unexpected_outcomes"] == []
    assert summary["processing_time_seconds"] >= 0
    assert summary["synthetic_only"] is True
    assert summary["phase2_native_pdf_status"] == "success"
    assert report["limitations"]
    assert "real-world OCR accuracy" in " ".join(report["limitations"]) or any(
        "not a real-world" in line.lower() or "not a general" in line.lower() or "not an estimate" in line.lower()
        for line in report["limitations"]
    )
    if not report["ocr_fixture"]["ran"]:
        assert report["ocr_fixture"]["token_recall"] is None
        assert "Tesseract" in report["ocr_fixture"]["reason"]
    else:
        assert 0 <= report["ocr_fixture"]["token_recall"] <= 1
        assert report["ocr_fixture"]["status"] in {"success", "partial"}


def test_phase2_evaluation_json_writer(tmp_path, capsys):
    destination = tmp_path / "phase2_eval.json"
    code = evaluate_phase2.main(["--json", str(destination)])
    assert code == 0 and destination.exists()
    data = json.loads(destination.read_text(encoding="utf-8"))
    assert data["summary"]["readable_fixture_success_rate"] == 1
    assert "Phase 2 fixture evaluation" in capsys.readouterr().out
