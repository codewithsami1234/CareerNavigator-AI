"""HTTP tests for the local API. GitHub calls are mocked or rejected before the network."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import config
import sample_data as sd
from api.app import create_app
from github_analysis.analyze import GitHubAnalysis
from schemas import STATUS_EMPTY, STATUS_FAILED, STATUS_NEEDS_OCR, STATUS_PARTIAL, STATUS_SUCCESS
from web import service

ORIGIN = "http://localhost:5173"


@pytest.fixture
def client():
    from testing_api import open_client

    return open_client()


def _resume(client, text=sd.FULL_RESUME, name="alex.txt", use_ocr=None):
    data = {} if use_ocr is None else {"use_ocr": use_ocr}
    return client.post(
        "/api/resume",
        files={"file": (name, text.encode("utf-8"), "text/plain")},
        data=data,
        headers={"Origin": ORIGIN},
    )


class TestResumeEndpoint:
    def test_text_resume_matches_the_service_payload(self, client):
        response = _resume(client)
        direct = service.analyze_upload("alex.txt", sd.FULL_RESUME.encode("utf-8")).to_dict()
        assert response.status_code == 200
        body = response.json()
        assert body == direct
        assert body["status"] == STATUS_SUCCESS
        assert body["contact"]["email"] == "alex.morgan@example.com"
        assert any(skill["name"] == "Python" for skill in body["skills"])
        assert response.headers["access-control-allow-origin"] == ORIGIN

    def test_partial_empty_failed_and_needs_ocr_statuses(self, client, monkeypatch):
        partial = _resume(client, sd.NO_SECTIONS_RESUME, "sam.txt")
        assert partial.status_code == 200
        assert partial.json()["status"] == STATUS_PARTIAL

        empty = _resume(client, " \n\n\t\n", "blank.txt")
        assert empty.json()["status"] == STATUS_EMPTY

        unsupported = client.post(
            "/api/resume",
            files={"file": ("notes.rtf", b"{\\rtf1 hi}", "application/rtf")},
        )
        assert unsupported.status_code == 200
        assert unsupported.json()["status"] == STATUS_FAILED
        assert "unsupported" in unsupported.json()["errors"][0].lower()

        seen = {}

        def resume(path, taxonomy_path=None):
            from schemas import ResumeAnalysis
            seen["path"] = Path(path)
            assert seen["path"].is_file()
            return ResumeAnalysis(status=STATUS_NEEDS_OCR, file_name=Path(path).name)

        monkeypatch.setattr(service, "analyze_resume", resume)
        scan = client.post(
            "/api/resume",
            files={"file": ("scan.pdf", b"%PDF-1.4\n", "application/pdf")},
            data={"use_ocr": "false"},
        )
        assert scan.status_code == 200
        assert scan.json()["status"] == STATUS_NEEDS_OCR
        assert scan.json()["file_name"] == "scan.pdf"
        assert not seen["path"].exists()
        assert not seen["path"].parent.exists()

    def test_use_ocr_selects_phase2_for_pdf_only(self, client, monkeypatch):
        calls = []

        def resume(path, taxonomy_path=None):
            calls.append("resume")
            from schemas import ResumeAnalysis
            return ResumeAnalysis(status=STATUS_SUCCESS, file_name=Path(path).name)

        def document(path, taxonomy_path=None, *, ocr=True, tesseract_cmd=None, ocr_lang=None):
            calls.append(("document", ocr))
            from schemas import ResumeAnalysis
            return ResumeAnalysis(status=STATUS_SUCCESS, file_name=Path(path).name)

        monkeypatch.setattr(service, "analyze_resume", resume)
        monkeypatch.setattr(service, "analyze_document", document)
        on = client.post(
            "/api/resume",
            files={"file": ("scan.pdf", b"%PDF-1.4\n", "application/pdf")},
            data={"use_ocr": "true"},
        )
        text = _resume(client, use_ocr="true")
        assert on.json()["status"] == STATUS_SUCCESS
        assert text.json()["status"] == STATUS_SUCCESS
        assert calls == [("document", True), "resume"]

    def test_image_upload_uses_phase2_and_rejects_mismatched_bytes(self, client, monkeypatch):
        calls = []
        parents = []

        def document(path, taxonomy_path=None, *, ocr=True, tesseract_cmd=None, ocr_lang=None):
            parents.append(Path(path).parent)
            calls.append((Path(path).suffix.lower(), ocr, Path(path).exists()))
            from schemas import ResumeAnalysis
            return ResumeAnalysis(
                status=STATUS_SUCCESS if ocr else STATUS_NEEDS_OCR,
                file_name=Path(path).name,
                source_format="image",
            )

        monkeypatch.setattr(service, "analyze_document", document)
        png = b"\x89PNG\r\n\x1a\nrest"
        off = client.post(
            "/api/resume",
            files={"file": ("photo.png", png, "image/png")},
            data={"use_ocr": "false"},
        )
        on = client.post(
            "/api/resume",
            files={"file": ("photo.png", png, "image/png")},
            data={"use_ocr": "true"},
        )
        assert off.status_code == 200
        assert off.json()["status"] == STATUS_NEEDS_OCR
        assert on.json()["status"] == STATUS_SUCCESS
        assert calls == [(".png", False, True), (".png", True, True)]
        assert parents and all(not parent.exists() for parent in parents)

        mismatch = client.post(
            "/api/resume",
            files={"file": ("photo.jpg", png, "image/jpeg")},
            data={"use_ocr": "true"},
        )
        assert mismatch.json()["status"] == STATUS_FAILED
        assert "do not match" in mismatch.json()["errors"][0].lower()
        assert len(calls) == 2

        mime = client.post(
            "/api/resume",
            files={"file": ("photo.png", png, "text/html")},
            data={"use_ocr": "true"},
        )
        assert mime.json()["status"] == STATUS_FAILED
        assert "content type" in mime.json()["errors"][0].lower()
        assert "text/html" not in mime.text

        disguised = client.post(
            "/api/resume",
            files={"file": ("notes.txt", b"%PDF-1.4\n" + b"A" * 80, "text/plain")},
        )
        assert disguised.json()["status"] == STATUS_FAILED
        assert "plain text" in disguised.json()["errors"][0].lower()

        word = client.post(
            "/api/resume",
            files={"file": ("bad.docx", b"not a word file with enough letters", "application/zip")},
        )
        assert word.json()["status"] == STATUS_FAILED
        assert "word document" in word.json()["errors"][0].lower()

    def test_missing_file_bad_flag_and_hidden_exception(self, client, monkeypatch):
        missing = client.post("/api/resume", files={"unused": (None, "")})
        assert missing.status_code == 400
        assert missing.json() == {"status": STATUS_FAILED, "errors": ["A resume file is required."]}
        urlencoded = client.post("/api/resume", data={"use_ocr": "false"})
        assert urlencoded.status_code == 415

        bad_flag = client.post(
            "/api/resume",
            files={"file": ("alex.txt", b"hello resume text\n", "text/plain")},
            data={"use_ocr": "maybe"},
        )
        assert bad_flag.status_code == 400
        assert "maybe" not in bad_flag.text

        wrong_type = client.post("/api/resume", json={"file": "not a file"})
        assert wrong_type.status_code == 415

        def boom(filename, data, *, use_ocr=False):
            raise RuntimeError("private resume sentence")

        monkeypatch.setattr(service, "analyze_upload", boom)
        failed = client.post(
            "/api/resume",
            files={"file": ("alex.txt", b"private resume sentence\n" * 3, "text/plain")},
        )
        assert failed.status_code == 500
        assert failed.json()["errors"] == ["The request could not be processed."]
        assert "private resume sentence" not in failed.text
        assert "Traceback" not in failed.text

    def test_oversized_upload_and_escaped_filename(self, client, monkeypatch):
        monkeypatch.setattr(config, "MAX_FILE_SIZE_BYTES", 32)
        oversized = client.post(
            "/api/resume",
            files={"file": ("big.txt", b"x" * 200, "text/plain")},
        )
        assert oversized.status_code == 200
        assert oversized.json()["status"] == STATUS_FAILED
        assert "too large" in oversized.json()["errors"][0].lower()
        assert "x" * 40 not in oversized.text

        escaped = client.post(
            "/api/resume",
            files={"file": (r"..\private\alex.txt", b"hello resume text enough\n", "text/plain")},
        )
        assert escaped.json()["file_name"] == "alex.txt"
        assert "private" not in escaped.json()["file_name"]

    def test_one_byte_over_the_real_limit_states_byte_counts(self, client):
        exact = config.MAX_FILE_SIZE_BYTES + 1
        one_over = client.post(
            "/api/resume",
            files={"file": ("one-over.txt", b"x" * exact, "text/plain")},
        )
        message = one_over.json()["errors"][0]
        assert one_over.status_code == 200
        assert one_over.json()["status"] == STATUS_FAILED
        assert "too large" in message.lower()
        assert str(exact) in message
        assert str(config.MAX_FILE_SIZE_BYTES) in message
        assert "10.0 MB" not in message


class TestJobEndpoint:
    def test_required_and_preferred_text(self, client):
        posting = "Requirements\n- Python\n\nPreferred\n- Docker\n"
        response = client.post("/api/job", json={"text": posting})
        assert response.status_code == 200
        body = response.json()
        assert body == service.analyze_job_input(text=posting).to_dict()
        assert body["status"] == STATUS_SUCCESS
        priorities = {item["skill_name"]: item["priority"] for item in body["requirements"]}
        assert priorities["Python"] == "required"
        assert priorities["Docker"] == "preferred"

    def test_empty_text_file_and_bad_request(self, client):
        empty = client.post("/api/job", json={"text": ""})
        assert empty.status_code == 200
        assert empty.json()["status"] == STATUS_EMPTY

        uploaded = client.post(
            "/api/job",
            files={"file": ("role.txt", b"Requirements\n- SQL\n", "text/plain")},
        )
        assert uploaded.status_code == 200
        assert uploaded.json()["status"] == STATUS_SUCCESS
        assert any(item["skill_name"] == "SQL" for item in uploaded.json()["requirements"])

        unsupported = client.post(
            "/api/job",
            files={"file": ("role.rtf", b"{\\rtf1 Python}", "application/rtf")},
        )
        assert unsupported.json()["status"] == STATUS_FAILED

        bad_text = client.post("/api/job", json={"text": 12})
        assert bad_text.status_code == 400
        assert "12" not in bad_text.text

        missing = client.post("/api/job")
        assert missing.status_code == 415


class TestGitHubEndpoint:
    def test_invalid_username_does_not_call_the_network(self, client, monkeypatch):
        def blocked(*args, **kwargs):
            raise AssertionError("network")

        monkeypatch.setattr("github_analysis.analyze.UrllibTransport.request", blocked)
        response = client.post("/api/github", json={"username": "not a user"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == STATUS_FAILED
        assert "username" in body["reason"].lower()
        assert "token" not in response.text.lower()

    def test_rate_limit_status_is_passed_through(self, client, monkeypatch):
        def limited(username):
            reason = "GitHub rate limit was reached. Wait and try again, or set GITHUB_TOKEN in the environment."
            return GitHubAnalysis(status="rate_limited", username="octocat", reason=reason, errors=[reason])

        monkeypatch.setattr(service, "read_github_profile", limited)
        response = client.post("/api/github", json={"username": "octocat"})
        assert response.status_code == 200
        assert response.json()["status"] == "rate_limited"
        assert response.json()["reason"].startswith("GitHub rate limit was reached.")
        assert "ghp_secret" not in response.text

    def test_bad_username_shape_is_rejected(self, client):
        response = client.post("/api/github", json={"username": 5})
        assert response.status_code == 400
        assert response.json()["status"] == STATUS_FAILED
        assert "5" not in response.text


class TestCareerReport:
    def test_round_trip_keeps_comparison_outcomes(self, client):
        resume = _resume(client).json()
        job = client.post(
            "/api/job",
            json={"text": "Requirements\n- Python\n- Webflow\n"},
        ).json()
        github = {
            "status": STATUS_FAILED,
            "username": None,
            "profile_url": None,
            "name": None,
            "bio": None,
            "public_repos": None,
            "repositories": [],
            "skills": [],
            "warnings": [],
            "errors": ["GitHub was not requested."],
            "limitations": [],
            "reason": "GitHub was not requested.",
        }
        response = client.post(
            "/api/career-report",
            json={"resume": resume, "job": job, "github": github, "weekly_hours": 4},
        )
        assert response.status_code == 200
        body = response.json()
        outcomes = {item["requirement"]["skill_name"]: item["outcome"] for item in body["comparison"]["matches"]}
        assert outcomes["Python"] == "matched"
        assert outcomes["Webflow"] == "missing"
        assert body["readiness"]["estimate"] == 50
        assert body["github_status"] == STATUS_FAILED
        assert body["resume_status"] == STATUS_SUCCESS
        assert any(item["skill_name"] == "Webflow" for item in body["recommendations"]["items"])
        assert "4" in body["roadmap"]["planning_note"]
        assert "No measured duration" in body["roadmap"]["planning_note"]

    def test_failed_resume_stays_unavailable_and_bad_objects_are_not_echoed(self, client):
        failed = client.post(
            "/api/resume",
            files={"file": ("notes.rtf", b"{\\rtf1 hi}", "application/rtf")},
        ).json()
        report = client.post("/api/career-report", json={"resume": failed})
        assert report.status_code == 200
        assert report.json()["readiness"]["status"] == "unavailable"
        assert report.json()["comparison"] is None

        secret = "PRIVATE RESUME LINE that must not echo"
        rejected = client.post("/api/career-report", json={"resume": secret})
        assert rejected.status_code == 400
        assert secret not in rejected.text
        assert "Traceback" not in rejected.text

        hours = client.post(
            "/api/career-report",
            json={"resume": failed, "weekly_hours": "4"},
        )
        assert hours.status_code == 400
        assert hours.json()["errors"] == ["weekly_hours must be a whole number or be omitted."]


class TestCors:
    def test_only_the_configured_origin_is_allowed(self, monkeypatch):
        monkeypatch.setenv("CAREERNAV_CORS_ORIGINS", "http://localhost:3000")
        local = TestClient(create_app(), raise_server_exceptions=False)
        allowed = local.post(
            "/api/github",
            json={"username": "not a user"},
            headers={"Origin": "http://localhost:3000"},
        )
        blocked = local.post(
            "/api/github",
            json={"username": "not a user"},
            headers={"Origin": "https://evil.example"},
        )
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
        assert "access-control-allow-origin" not in blocked.headers

    def test_wildcard_is_not_accepted(self, monkeypatch):
        monkeypatch.setenv("CAREERNAV_CORS_ORIGINS", "*")
        local = TestClient(create_app(), raise_server_exceptions=False)
        response = local.post(
            "/api/github",
            json={"username": "not a user"},
            headers={"Origin": "https://evil.example"},
        )
        assert response.headers.get("access-control-allow-origin") in (None, "http://localhost:5173")
        assert response.headers.get("access-control-allow-origin") != "*"
