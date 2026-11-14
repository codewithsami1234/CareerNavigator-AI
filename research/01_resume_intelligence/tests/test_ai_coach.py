"""AI Coach: configuration, prompt privacy, reply parsing, and the HTTP route.

No test reaches a real LLM. Upstream replies come from ``httpx.MockTransport``.
"""
import json

import httpx
import pytest

import sample_data as sd
from ai_coach import coach as coach_module
from ai_coach.coach import build_prompt_context, coach_report
from web import service

JOB_TEXT = "Requirements\n- Python\n- Webflow\n- Kubernetes\n"


def _career_dict():
    resume = service.analyze_upload("alex.txt", sd.FULL_RESUME.encode("utf-8"))
    job = service.analyze_job_input(text=JOB_TEXT)
    return service.build_career_report(resume, job, None).to_dict()


def _configure(monkeypatch):
    monkeypatch.setenv("AI_API_BASE", "https://llm.example/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")


def _reply(content, status=200):
    def handler(request):
        handler.request = request
        return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})

    handler.request = None
    return handler


def _good_content(report):
    titles = [m["title"] for m in report["roadmap"]["milestones"]]
    return json.dumps({
        "summary": "You have a solid Python base. Focus on the missing tools first.",
        "milestones": [
            {"title": titles[0], "why_it_matters": "The posting requires it.", "tips": ["Build a small demo", "Write it up"]},
            {"title": "A milestone the model invented", "why_it_matters": "Should be dropped.", "tips": []},
        ],
        "interview_questions": [
            {"skill": "Kubernetes", "question": "How would you deploy a service?", "good_answer_covers": "Pods, services, rollouts."},
        ],
    })


class TestConfiguration:
    def test_unconfigured_returns_unavailable_without_network(self):
        def boom(request):
            raise AssertionError("no network call expected")

        result = coach_report(_career_dict(), transport=httpx.MockTransport(boom))
        assert result.status == "unavailable"
        assert "AI_API_KEY" in result.reason

    def test_report_without_roadmap_is_unavailable(self, monkeypatch):
        _configure(monkeypatch)
        result = coach_report({"roadmap": {"status": "unavailable", "milestones": []}})
        assert result.status == "unavailable"


class TestPrompt:
    def test_prompt_context_excludes_contact_details(self):
        context = json.dumps(build_prompt_context(_career_dict(), "Backend Developer"))
        assert "alex.morgan@example.com" not in context
        assert "Alex Morgan" not in context
        assert "Backend Developer" in context
        assert "Kubernetes" in context

    def test_request_uses_openai_compatible_shape(self, monkeypatch):
        _configure(monkeypatch)
        report = _career_dict()
        handler = _reply(_good_content(report))
        coach_report(report, transport=httpx.MockTransport(handler))
        sent = handler.request
        assert str(sent.url) == "https://llm.example/v1/chat/completions"
        assert sent.headers["authorization"] == "Bearer test-key"
        body = json.loads(sent.content)
        assert body["model"] == "test-model"
        assert [m["role"] for m in body["messages"]] == ["system", "user"]


class TestReplyParsing:
    def test_success_keeps_only_known_milestones(self, monkeypatch):
        _configure(monkeypatch)
        report = _career_dict()
        result = coach_report(report, transport=httpx.MockTransport(_reply(_good_content(report))))
        assert result.status == "success"
        assert result.model == "test-model"
        assert [m.title for m in result.milestones] == [report["roadmap"]["milestones"][0]["title"]]
        assert result.interview_questions[0].skill == "Kubernetes"
        assert result.summary.startswith("You have")

    def test_code_fenced_json_is_accepted(self, monkeypatch):
        _configure(monkeypatch)
        report = _career_dict()
        fenced = "Here you go:\n```json\n" + _good_content(report) + "\n```"
        result = coach_report(report, transport=httpx.MockTransport(_reply(fenced)))
        assert result.status == "success"

    def test_non_json_reply_fails_cleanly(self, monkeypatch):
        _configure(monkeypatch)
        result = coach_report(_career_dict(), transport=httpx.MockTransport(_reply("Sorry, I can't help.")))
        assert result.status == "failed"
        assert "JSON" in result.reason

    @pytest.mark.parametrize("status,needle", [(429, "credits"), (401, "API key"), (500, "error")])
    def test_upstream_errors_map_to_readable_reasons(self, monkeypatch, status, needle):
        _configure(monkeypatch)
        result = coach_report(_career_dict(), transport=httpx.MockTransport(_reply("{}", status=status)))
        assert result.status == "failed"
        assert needle in result.reason
        assert "test-key" not in result.reason

    def test_timeout_fails_cleanly(self, monkeypatch):
        _configure(monkeypatch)

        def slow(request):
            raise httpx.ReadTimeout("slow", request=request)

        result = coach_report(_career_dict(), transport=httpx.MockTransport(slow))
        assert result.status == "failed"
        assert "too long" in result.reason


class TestRoute:
    def _client(self):
        from testing_api import open_client

        return open_client()

    def test_route_returns_coach_result(self, monkeypatch):
        _configure(monkeypatch)
        report = _career_dict()
        transport = httpx.MockTransport(_reply(_good_content(report)))
        real_client = httpx.Client
        monkeypatch.setattr(coach_module.httpx, "Client", lambda **kw: real_client(**{**kw, "transport": transport}))

        client = self._client()
        resume = client.post(
            "/api/resume",
            files={"file": ("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")},
        ).json()
        job = client.post("/api/job", json={"text": JOB_TEXT}).json()
        response = client.post("/api/ai-coach", json={"resume": resume, "job": job, "target_career": "Backend Developer"})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "success"
        assert body["interview_questions"]
        assert "disclaimer" in body

    def test_route_unconfigured_and_bad_input(self):
        client = self._client()
        resume = client.post(
            "/api/resume",
            files={"file": ("alex.txt", sd.FULL_RESUME.encode("utf-8"), "text/plain")},
        ).json()
        job = client.post("/api/job", json={"text": JOB_TEXT}).json()
        unconfigured = client.post("/api/ai-coach", json={"resume": resume, "job": job})
        assert unconfigured.status_code == 200
        assert unconfigured.json()["status"] == "unavailable"

        missing = client.post("/api/ai-coach", json={"job": job})
        assert missing.status_code == 400

        long_label = client.post("/api/ai-coach", json={"resume": resume, "target_career": "x" * 300})
        assert long_label.status_code == 400

    def test_route_requires_sign_in(self):
        from fastapi.testclient import TestClient

        from api.app import create_app

        anonymous = TestClient(create_app(), raise_server_exceptions=False)
        response = anonymous.post("/api/ai-coach", json={})
        assert response.status_code in (401, 403)
