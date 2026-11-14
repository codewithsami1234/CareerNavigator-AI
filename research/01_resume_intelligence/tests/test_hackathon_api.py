"""Health and report endpoints. The report copies the existing readiness estimate."""
from fastapi.testclient import TestClient

import sample_data as sd
from api.app import create_app
from web import service
from web.ui.report_export import readable_report

ORIGIN = "http://localhost:5173"
JOB_TEXT = "Requirements\n- Python\n- Webflow\n"


def _client():
    from testing_api import open_client

    return open_client()


def _resume(client):
    return client.post(
        "/api/resume",
        files={"file": ("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")},
    )


class TestHealth:
    def test_health_names_the_rule_based_scorer_and_rejects_other_origins(self):
        client = _client()
        allowed = client.get("/api/health", headers={"Origin": ORIGIN})
        assert allowed.status_code == 200
        assert allowed.json() == {
            "status": "ok",
            "service": "CareerNavigator AI",
            "scoring": "rule-based readiness estimate",
        }
        assert allowed.headers["access-control-allow-origin"] == ORIGIN
        blocked = client.get("/api/health", headers={"Origin": "https://evil.example"})
        assert blocked.status_code == 200
        assert "access-control-allow-origin" not in blocked.headers


class TestReport:
    def test_report_copies_the_pipeline_estimate_and_the_typed_label(self):
        client = _client()
        resume = _resume(client).json()
        job = client.post("/api/job", json={"text": JOB_TEXT}).json()
        response = client.post(
            "/api/report",
            json={
                "resume": resume,
                "job": job,
                "weekly_hours": 4,
                "job_title": "Backend Developer",
                "company": "Example Labs",
                "target_career": "Software engineering",
            },
        )
        assert response.status_code == 200
        body = response.json()
        direct = service.build_career_report(
            service.analyze_upload("alex.txt", sd.FULL_RESUME.encode("utf-8")),
            service.analyze_job_input(text=JOB_TEXT),
            weekly_hours=4,
        )
        estimate = direct.readiness.estimate
        assert body["analysis_status"] == "success"
        assert body["report"]["career_report"]["readiness"]["estimate"] == estimate
        assert f"Estimate: {estimate}" in body["markdown"]
        assert "does not calculate a second score" in body["markdown"]
        assert "not an ATS score" in body["markdown"]
        assert "Backend Developer" in body["markdown"]
        assert "typed into the form" in body["markdown"]
        assert "Python" in body["skills_csv"]
        assert "matched" in body["comparison_csv"]
        assert "Webflow" in body["markdown"]
        assert "No measured duration" in body["markdown"]
        assert body["report"]["entered_labels"]["company"] == "Example Labs"
        assert "Traceback" not in response.text

    def test_bad_labels_are_rejected_without_echoing_the_value(self):
        client = _client()
        resume = _resume(client).json()
        secret = "PRIVATE LABEL VALUE"
        rejected = client.post("/api/report", json={"resume": resume, "job_title": 3})
        assert rejected.status_code == 400
        assert "3" not in rejected.text
        assert secret not in rejected.text
        too_long = client.post("/api/report", json={"resume": resume, "company": "x" * 201})
        assert too_long.status_code == 400
        assert "x" * 40 not in too_long.text

    def test_failed_resume_report_does_not_invent_skills(self):
        client = _client()
        failed = client.post(
            "/api/resume",
            files={"file": ("notes.rtf", b"{\\rtf1 hi}", "application/rtf")},
        ).json()
        response = client.post("/api/report", json={"resume": failed})
        assert response.status_code == 200
        body = response.json()
        assert body["analysis_status"] == "failed"
        assert "Unsupported" in body["markdown"]
        assert "No taxonomy skills were extracted." in body["markdown"]
        assert body["skills_csv"] is None
        assert body["comparison_csv"] is None

    def test_readable_report_without_a_job_has_no_estimate(self):
        resume = service.analyze_upload("alex.txt", sd.FULL_RESUME.encode("utf-8"))
        career = service.build_career_report(resume, None, None)
        text = readable_report(resume, None, None, None, career)
        assert "Estimate: Not scored" in text
        assert "No job description was supplied" in text
        assert "Listings are not fetched" in text
