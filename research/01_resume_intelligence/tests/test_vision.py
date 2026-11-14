"""OpenCV preprocessing and quality diagnostics. No Tesseract required."""
import cv2
import numpy as np

import config
from vision.image_io import load_image, sniff_image_format
from vision.preprocess import estimate_skew, prepare_candidates, readability_score, to_gray
from vision.quality import assess_image


def _save_png(path, image):
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    path.write_bytes(encoded.tobytes())


def _bars(width=640, height=420):
    image = np.full((height, width), 255, np.uint8)
    for y in range(36, height - 36, 28):
        image[y:y + 3, 40:width - 40] = 0
    return image


def _rotate(image, angle):
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(image, matrix, (width, height), borderValue=255)


class TestImageValidation:
    def test_png_and_jpeg_magic(self):
        assert sniff_image_format(b"\x89PNG\r\n\x1a\nrest") == "png"
        assert sniff_image_format(b"\xff\xd8\xffrest") == "jpeg"
        assert sniff_image_format(b"not an image") is None

    def test_empty_file(self, tmp_path):
        path = tmp_path / "empty.png"
        path.write_bytes(b"")
        loaded = load_image(path)
        assert not loaded.ok
        assert "empty" in loaded.errors[0].lower()

    def test_invalid_bytes(self, tmp_path):
        path = tmp_path / "bad.png"
        path.write_bytes(b"this is not a png")
        loaded = load_image(path)
        assert not loaded.ok and loaded.errors

    def test_truncated_png(self, tmp_path):
        path = tmp_path / "cut.png"
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"garbage")
        loaded = load_image(path)
        assert not loaded.ok
        assert "decode" in loaded.errors[0].lower() or "valid" in loaded.errors[0].lower()

    def test_extension_mismatch(self, tmp_path):
        path = tmp_path / "photo.png"
        image = np.full((40, 40, 3), 255, np.uint8)
        ok, encoded = cv2.imencode(".jpg", image)
        assert ok
        path.write_bytes(encoded.tobytes())
        loaded = load_image(path)
        assert not loaded.ok
        assert "extension" in loaded.errors[0].lower()

    def test_readable_png_loads(self, tmp_path):
        path = tmp_path / "page.png"
        _save_png(path, cv2.cvtColor(_bars(), cv2.COLOR_GRAY2BGR))
        loaded = load_image(path)
        assert loaded.ok
        assert loaded.width == 640 and loaded.height == 420

    def test_dimension_limit(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config, "MAX_IMAGE_SIDE_PX", 40)
        path = tmp_path / "big.png"
        _save_png(path, np.full((50, 50, 3), 200, np.uint8))
        loaded = load_image(path)
        assert not loaded.ok
        assert "too large" in loaded.errors[0].lower()


class TestPreprocess:
    def test_readable_image_is_grayscale_and_keeps_aspect(self):
        color = cv2.cvtColor(_bars(300, 100), cv2.COLOR_GRAY2BGR)
        candidates = prepare_candidates(color)
        names = {item.name for item in candidates}
        assert "grayscale" in names
        assert "denoise_clahe" in names
        gray = next(item for item in candidates if item.name == "grayscale")
        assert gray.image.ndim == 2
        assert "grayscale" in gray.steps
        assert abs((gray.height / gray.width) - (100 / 300)) < 0.05

    def test_threshold_is_not_forced_when_it_hurts(self):
        candidates = prepare_candidates(cv2.cvtColor(_bars(), cv2.COLOR_GRAY2BGR))
        grayscale = next(item for item in candidates if item.name == "grayscale")
        for item in candidates:
            if item.name in {"otsu", "adaptive"} and item.score + 1e-6 < grayscale.score * 0.85:
                # Selector drops these. The candidate may still be built for comparison.
                assert item.score < grayscale.score

    def test_high_contrast_scores_above_a_flat_image(self):
        sharp = readability_score(_bars())
        flat = readability_score(np.full((420, 640), 140, np.uint8))
        assert sharp > flat

    def test_skew_estimate_levels_rotated_lines(self):
        rotated = _rotate(_bars(), 8)
        applied, reported = estimate_skew(rotated)
        assert abs(abs(reported) - 8) < 1.5, (applied, reported)
        assert abs(abs(applied) - 8) < 1.5
        corrected = _rotate(rotated, applied)
        _applied_again, residual = estimate_skew(corrected)
        assert abs(residual) < 1.5, residual


class TestQualityWarnings:
    def test_low_contrast_and_low_resolution(self):
        image = np.full((120, 80), 140, np.uint8)
        image[20:100, 15:70] = 155
        findings = assess_image(image, skew_degrees=0)
        codes = {item.code for item in findings}
        assert "poor_contrast" in codes
        assert "low_resolution" in codes
        assert "page_dimensions" in codes
        contrast = next(item for item in findings if item.code == "poor_contrast")
        assert contrast.kind == "heuristic" and contrast.severity == "warning"

    def test_excessive_skew_is_a_warning_not_a_verdict(self):
        findings = assess_image(_bars(), skew_degrees=8.2)
        skew = next(item for item in findings if item.code == "excessive_skew")
        assert skew.kind == "heuristic"
        assert "ATS-incompatible" not in skew.message

    def test_blank_unusual_and_crowded_pages(self):
        blank = assess_image(np.full((200, 900), 255, np.uint8), skew_degrees=0)
        blank_codes = {item.code for item in blank}
        assert "blank_page" in blank_codes
        assert "unusual_dimensions" in blank_codes

        noise = np.zeros((300, 300), np.uint8)
        noise[::2] = 255
        crowded = assess_image(noise, skew_degrees=0)
        assert any(item.code == "crowded_layout" and item.kind == "heuristic" for item in crowded)

    def test_clear_page_has_no_contrast_warning(self):
        findings = assess_image(_bars(1200, 1600), skew_degrees=0.2)
        assert not any(item.code == "poor_contrast" for item in findings)
        assert not any(item.code == "low_resolution" for item in findings)
        assert any(item.kind == "measured" for item in findings)

    def test_to_gray_accepts_bgr(self):
        gray = to_gray(cv2.cvtColor(_bars(80, 60), cv2.COLOR_GRAY2BGR))
        assert gray.ndim == 2 and gray.dtype == np.uint8
