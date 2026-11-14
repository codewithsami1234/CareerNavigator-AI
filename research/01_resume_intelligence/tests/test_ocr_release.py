"""Unreadable OCR is a failure. Useful resume text is kept."""
import cv2
import numpy as np
import pytest

from ocr.readability import BLANK_IMAGE_MESSAGE, UNREADABLE_MESSAGE, unreliable_ocr_reason
from ocr.tesseract_ocr import locate_tesseract
from pipeline import analyze_document
from schemas import STATUS_EMPTY, STATUS_FAILED, STATUS_PARTIAL, STATUS_SUCCESS


def test_confidence_alone_does_not_reject_resume_wording():
    text = (
        "Jordan Hale\nSoftware engineer\nSkills\n"
        "Python, JavaScript, SQL, Git, Docker\n"
        "Experience\nBuilt REST APIs with Python and SQL.\n"
        "Education\nBachelor of Science, State University\n"
    )
    assert unreliable_ocr_reason(text, 32.0, {"ink_ratio": 0.7}) is None
    assert unreliable_ocr_reason(text, 90.0, {"ink_ratio": 0.08}) is None


def test_noise_signals_are_rejected_together():
    garbage = "xqz vrt kpl mnb wqf jhz lkp qzx vbn mcx rty plk " * 8
    assert unreliable_ocr_reason(garbage, 19.0, {"ink_ratio": 0.83}) == UNREADABLE_MESSAGE
    assert unreliable_ocr_reason(garbage, 80.0, {"ink_ratio": 0.83}) is None
    assert unreliable_ocr_reason(garbage, 19.0, {"ink_ratio": 0.05}) == UNREADABLE_MESSAGE


def _write_png(path, image):
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())
    return path


def _write_jpeg(path, image, quality=60):
    ok, encoded = cv2.imencode(".jpg", image, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok
    path.write_bytes(encoded.tobytes())
    return path


def _resume_image():
    image = np.full((1600, 1200, 3), 255, np.uint8)
    lines = [
        (70, "Jordan Hale"),
        (150, "Software engineer"),
        (250, "Skills"),
        (320, "Python, JavaScript, SQL, Git, Docker"),
        (420, "Experience"),
        (490, "Northwind Labs, 2021 to 2024"),
        (560, "Built REST APIs with Python and SQL."),
        (630, "Shipped a dashboard using JavaScript."),
        (730, "Education"),
        (800, "BSc Computer Science, State University"),
    ]
    for top, line in lines:
        cv2.putText(image, line, (80, top), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2, cv2.LINE_AA)
    return image


def _tesseract_or_skip():
    path, _message = locate_tesseract()
    if not path:
        pytest.skip("Tesseract is not installed")


def test_blank_image_explains_that_nothing_was_read(tmp_path):
    _tesseract_or_skip()
    image = np.full((900, 700, 3), 255, np.uint8)
    analysis = analyze_document(_write_png(tmp_path / "blank.png", image), ocr=True)
    assert analysis.status in {STATUS_EMPTY, STATUS_FAILED}
    assert analysis.skills == []
    assert analysis.experience == []
    joined = " ".join(analysis.errors + analysis.warnings).lower()
    assert "clearer" in joined or BLANK_IMAGE_MESSAGE.lower() in joined


def test_noise_image_is_not_a_successful_resume(tmp_path):
    _tesseract_or_skip()
    noise = np.random.default_rng(7).integers(0, 255, (640, 480, 3), dtype=np.uint8)
    analysis = analyze_document(_write_jpeg(tmp_path / "noise.jpg", noise, quality=40), ocr=True)
    assert analysis.status == STATUS_FAILED
    assert analysis.skills == []
    assert analysis.education == []
    assert analysis.experience == []
    assert any("could not be read reliably" in error.lower() for error in analysis.errors)
    assert (analysis.text_length or 0) == 0


def test_clear_scan_and_rotated_photo_keep_real_skills(tmp_path):
    _tesseract_or_skip()
    clear = _resume_image()
    scanned = analyze_document(_write_png(tmp_path / "scan.png", clear), ocr=True)
    assert scanned.status in {STATUS_SUCCESS, STATUS_PARTIAL}
    names = {skill.name for skill in scanned.skills}
    assert {"Python", "JavaScript", "SQL"} <= names

    center = (clear.shape[1] / 2, clear.shape[0] / 2)
    matrix = cv2.getRotationMatrix2D(center, 3.0, 1.0)
    rotated = cv2.warpAffine(clear, matrix, (clear.shape[1], clear.shape[0]), borderValue=(232, 224, 208))
    photo = analyze_document(_write_jpeg(tmp_path / "photo.jpg", rotated, quality=55), ocr=True)
    assert photo.status in {STATUS_SUCCESS, STATUS_PARTIAL}
    photo_names = {skill.name for skill in photo.skills}
    assert "Python" in photo_names
    assert "SQL" in photo_names


def test_partially_readable_resume_is_not_discarded(tmp_path):
    _tesseract_or_skip()
    image = _resume_image()
    noise = np.random.default_rng(3).integers(0, 255, (500, image.shape[1], 3), dtype=np.uint8)
    image[1100:1600, :, :] = noise
    analysis = analyze_document(_write_jpeg(tmp_path / "partial.jpg", image, quality=70), ocr=True)
    assert analysis.status in {STATUS_SUCCESS, STATUS_PARTIAL}
    assert any(skill.name == "Python" for skill in analysis.skills)


def test_missing_tesseract_dependency_is_explained(tmp_path):
    image = np.full((200, 200, 3), 255, np.uint8)
    analysis = analyze_document(
        _write_png(tmp_path / "needs-engine.png", image),
        ocr=True,
        tesseract_cmd=r"C:\cn-verify-missing\tesseract.exe",
    )
    assert analysis.status == STATUS_FAILED
    assert analysis.skills == []
    joined = " ".join(analysis.errors)
    assert "Tesseract" in joined
    assert "not found" in joined.lower() or "not installed" in joined.lower()
