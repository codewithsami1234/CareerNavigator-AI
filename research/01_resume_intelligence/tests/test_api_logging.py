"""API logs record status and size, not resume text, file names, or tokens."""
import logging

from fastapi.testclient import TestClient

from api.app import create_app


def _client():
    from testing_api import open_client

    return open_client()


class TestApiLogging:
    def test_resume_log_omits_file_name_and_text(self, caplog):
        caplog.set_level(logging.INFO, logger="careernavigator.api")
        marker = "UNIQUE_RESUME_SENTENCE about quantum pottery"
        response = _client().post(
            "/api/resume",
            files={"file": ("secret-candidate-name.txt", marker.encode("utf-8"), "text/plain")},
        )
        assert response.status_code == 200
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "resume_upload" in logged
        assert ".txt" in logged
        assert marker not in logged
        assert "secret-candidate-name" not in logged

    def test_github_log_omits_token_and_rejects_a_bad_username(self, caplog, monkeypatch):
        caplog.set_level(logging.INFO, logger="careernavigator.api")
        monkeypatch.setenv("GITHUB_TOKEN", "test-token-should-not-be-logged")
        response = _client().post("/api/github", json={"username": "not a user"})
        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        logged = "\n".join(record.getMessage() for record in caplog.records)
        assert "github_lookup status=failed" in logged
        assert "test-token-should-not-be-logged" not in logged
        assert "not a user" not in logged
