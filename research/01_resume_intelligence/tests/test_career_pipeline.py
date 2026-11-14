"""Offline tests for GitHub reading, readiness, recommendations, and the roadmap.

GitHub calls use a fake transport. Nothing in this module contacts the network.
"""
from __future__ import annotations

from datetime import date

import pytest

import config
from github_analysis import analyze_github, clear_github_cache
from github_analysis.analyze import GitHubAnalysis, GitHubSkillEvidence, UrllibTransport
from pipeline import analyze_job, analyze_text, career_report, compare
from schemas import (
    OUTCOME_INDETERMINATE, OUTCOME_MATCHED, OUTCOME_MISSING, PRIORITY_PREFERRED, PRIORITY_REQUIRED,
    PRIORITY_UNSPECIFIED,
    STATUS_SUCCESS,
)

AS_OF = date(2026, 1, 15)

PROJECTS_ONLY = """
ALEX EXAMPLE
alex.example@example.com | Example City

PROJECTS
Library System | C++
- Console library built with object-oriented programming. No employment section is included.

Puzzle Game | React.js, CSS, JavaScript
- Interactive browser puzzle for a class assignment.
"""

EMPLOYED = """
JANE EXAMPLE
jane.example@example.com | Example City

SKILLS
Python, SQL, Git

EXPERIENCE
Software Engineer, Example Ltd (Jan 2020 - Jan 2024)
- Built services in Python and SQL for internal tools.

EDUCATION
BS Computer Science, Example University (2016 - 2020)
"""

SKILLS_ONLY = """
SAM EXAMPLE
sam.example@example.com | Example City

TECHNICAL SKILLS
Python, SQL, Git

EDUCATION
BS Computer Science, Example University (2018 - 2022)
"""

FRONTEND_POSTING = """
Frontend Developer (React)

About the company
We are a fast-growing product company. Our stack includes TypeScript, Docker, and GitLab.
Join us and learn CI/CD and Microsoft Azure on the job.

Benefits
- Competitive salary and health insurance
- Learn Redux, TypeScript, and Docker on the job

Requirements
- 3+ years of professional software development experience, including 2+ years with React
- Strong proficiency in JavaScript, including React hooks, TypeScript, and modern JavaScript (ES6+)
- Experience with Flux or Redux or similar state-management approaches
- Understanding of functional programming principles
- Experience consuming REST APIs
- Familiarity with Git

Preferred
- GitLab
- Docker and CI/CD
"""

FRONTEND_RESUME = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
JavaScript, React.js, CSS, Git, GitHub, Node.js, C++

PROJECTS

Library System | C++
- Console library built with object-oriented programming

Puzzle Game | React.js, CSS, JavaScript
- Interactive browser puzzle

Notes App | Node.js
- Stores notes for a class assignment
"""


class FakeGitHub:
    def __init__(self, routes, error=None):
        self.routes = routes
        self.error = error
        self.calls = []

    def request(self, url, headers):
        self.calls.append((url, dict(headers)))
        if self.error is not None:
            raise self.error
        match = None
        for key in self.routes:
            if key in url and (match is None or len(key) > len(match)):
                match = key
        if match is None:
            return 404, {"message": "missing"}, {}
        return self.routes[match]


def _routes(repos=None, languages=None, readme="Uses PostgreSQL for the API.", user_status=200, repo_status=200):
    if repos is None:
        repos = [{
            "name": "demo",
            "private": False,
            "fork": False,
            "full_name": "octocat/demo",
            "html_url": "https://github.com/octocat/demo",
            "description": "A Flask service",
            "topics": ["python", "docker"],
            "stargazers_count": 424242,
        }]
    if languages is None:
        languages = {"Python": 1200, "JavaScript": 40}
    user = {
        "login": "octocat",
        "html_url": "https://github.com/octocat",
        "name": "The Octocat",
        "bio": "I build Django applications",
        "public_repos": 3,
    }
    return {
        "https://api.github.com/users/octocat/repos": (repo_status, repos, {}),
        "https://api.github.com/repos/octocat/demo/languages": (200, languages, {}),
        "https://api.github.com/repos/octocat/demo/readme": (200, readme, {}),
        "https://api.github.com/users/octocat": (user_status, user, {}),
    }


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_github_cache()
    yield
    clear_github_cache()


def _names(report):
    return [item.skill_name for item in report.recommendations.items]


class TestGitHubAnalysis:
    def test_success_keeps_observed_evidence_and_skips_private_and_forks(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        repos = [
            {"name": "hidden", "private": True, "fork": False, "full_name": "octocat/hidden"},
            {
                "name": "forked", "private": False, "fork": True, "full_name": "octocat/forked",
                "html_url": "https://github.com/octocat/forked",
            },
            {
                "name": "demo", "private": False, "fork": False, "full_name": "octocat/demo",
                "html_url": "https://github.com/octocat/demo",
                "description": "A Flask service", "topics": ["python", "docker"],
                "stargazers_count": 424242,
                "pushed_at": "2024-01-02T03:04:05Z",
            },
        ]
        transport = FakeGitHub(_routes(repos=repos))
        result = analyze_github("https://github.com/octocat/", transport=transport, token="")
        assert result.status == STATUS_SUCCESS
        assert result.username == "octocat"
        assert [repo.name for repo in result.repositories] == ["demo"]
        assert result.repositories[0].pushed_at == "2024-01-02T03:04:05Z"
        assert result.repositories[0].description == "A Flask service"
        assert "Private repositories were skipped." in result.warnings
        assert "Forks were not analyzed." in result.warnings
        by_source = {}
        for skill in result.skills:
            assert skill.observed is True
            assert skill.repository_url == "https://github.com/octocat/demo"
            by_source.setdefault((skill.skill_name, skill.source_field), skill)
        assert by_source[("Flask", "description")].note is None
        assert by_source[("Docker", "topics")].source_field == "topics"
        assert "not a proficiency" in by_source[("Python", "languages")].note
        assert by_source[("PostgreSQL", "readme")].source_field == "readme"
        assert "Django" not in {skill.skill_name for skill in result.skills}
        payload = result.to_json()
        assert "424242" not in payload
        assert "proficiency" in " ".join(result.limitations).lower()
        assert all("Authorization" not in headers for _url, headers in transport.calls)

    def test_invalid_username_does_not_call_the_network(self):
        transport = FakeGitHub({}, error=AssertionError("network"))
        for value in ("", "not a user", "bad name", "https://gitlab.com/octocat", "https://github.com/octocat/demo", "about"):
            result = analyze_github(value, transport=transport, token="")
            assert result.status == "failed"
            assert result.errors
        assert transport.calls == []

    def test_missing_user_and_unavailable_repository(self):
        missing = FakeGitHub(_routes(user_status=404))
        result = analyze_github("@octocat", transport=missing, token="")
        assert result.status == "failed"
        assert "octocat" in result.reason

        routes = _routes()
        routes["https://api.github.com/repos/octocat/demo/languages"] = (
            404, {"message": "Not Found"}, {},
        )
        routes["https://api.github.com/repos/octocat/demo/readme"] = (
            404, {"message": "Not Found"}, {},
        )
        partial = analyze_github("octocat", transport=FakeGitHub(routes), token="")
        assert partial.status == STATUS_SUCCESS
        assert partial.repositories[0].warnings
        assert any(skill.skill_name == "Flask" for skill in partial.skills)

    def test_rate_limit_timeout_and_token_redaction(self, monkeypatch):
        limited = FakeGitHub({
            "https://api.github.com/users/octocat": (403, {"message": "API rate limit exceeded"}, {"x-ratelimit-remaining": "0"}),
        })
        result = analyze_github("octocat", transport=limited, token="")
        assert result.status == "rate_limited"
        assert result.repositories == []

        class TimeoutTransport:
            def request(self, url, headers):
                raise TimeoutError("timed out ghp_secretvalue")

        secret = "ghp_secretvalue"
        timed = analyze_github("octocat", transport=TimeoutTransport(), token=secret)
        assert timed.status == "failed"
        assert "timed out" in timed.reason
        assert secret not in timed.to_json()
        assert "[token]" in timed.reason

        monkeypatch.setenv("GITHUB_TOKEN", secret)
        seen = FakeGitHub(_routes())
        authed = analyze_github("octocat", transport=seen)
        assert seen.calls[0][1]["Authorization"] == f"Bearer {secret}"
        assert secret not in authed.to_json()
        clear_github_cache()
        ignored = FakeGitHub(_routes())
        analyze_github("octocat", transport=ignored, token="")
        assert ignored.calls
        assert "Authorization" not in ignored.calls[0][1]

    def test_mocked_http_failures_do_not_invent_a_profile(self):
        limited = analyze_github("octocat", transport=FakeGitHub({
            "https://api.github.com/users/octocat": (429, {"message": "too many requests"}, {}),
        }), token="")
        assert limited.status == "rate_limited"
        assert limited.name is None
        assert limited.bio is None
        assert limited.repositories == []
        assert limited.skills == []
        assert "rate limit" in (limited.reason or "").lower()

        denied = analyze_github("octocat", transport=FakeGitHub({
            "https://api.github.com/users/octocat": (
                403, {"message": "API rate limit exceeded for this account"}, {},
            ),
        }), token="")
        assert denied.status == "rate_limited"
        assert denied.name is None
        assert denied.repositories == []
        assert denied.skills == []

        class DnsFailure:
            def request(self, url, headers):
                raise OSError("getaddrinfo failed")

        offline = analyze_github("octocat", transport=DnsFailure(), token="")
        assert offline.status == "failed"
        assert offline.name is None
        assert offline.bio is None
        assert offline.repositories == []
        assert offline.skills == []
        assert "could not be reached" in (offline.reason or "").lower()
        assert "getaddrinfo" in (offline.reason or "").lower()

        unavailable = analyze_github("octocat", transport=FakeGitHub({
            "https://api.github.com/users/octocat": (503, {"message": "unavailable"}, {}),
        }), token="")
        assert unavailable.status == "failed"
        assert unavailable.name is None
        assert unavailable.repositories == []
        assert unavailable.skills == []
        assert "503" in (unavailable.reason or "")

    def test_repository_list_failure_keeps_the_profile(self):
        routes = _routes(repo_status=429)
        routes["https://api.github.com/users/octocat/repos"] = (
            429, {"message": "rate limit"}, {},
        )
        limited = analyze_github("octocat", transport=FakeGitHub(routes), token="")
        assert limited.status == STATUS_SUCCESS
        assert limited.username == "octocat"
        assert limited.repositories == []
        assert any("rate limit" in warning.lower() for warning in limited.warnings)

        class LateTimeout:
            def request(self, url, headers):
                if "/repos?" in url or "/repos?" in url:
                    raise TimeoutError("timed out")
                if url.endswith("/users/octocat"):
                    return 200, {"login": "octocat", "html_url": "https://github.com/octocat", "public_repos": 1}, {}
                raise TimeoutError("timed out")

        late = analyze_github("octocat", transport=LateTimeout(), token="")
        assert late.status == STATUS_SUCCESS
        assert late.profile_url
        assert any("timed out" in warning.lower() for warning in late.warnings)

    def test_cache_expires(self):
        clock = {"now": 1_000.0}

        def now():
            return clock["now"]

        transport = FakeGitHub(_routes(repos=[]))
        first = analyze_github("octocat", transport=transport, token="", clock=now)
        assert first.status == STATUS_SUCCESS
        calls = len(transport.calls)
        clock["now"] = 1_100.0
        analyze_github("octocat", transport=transport, token="", clock=now)
        assert len(transport.calls) == calls
        clock["now"] = 1_000.0 + config.GITHUB_CACHE_SECONDS + 1
        analyze_github("octocat", transport=transport, token="", clock=now)
        assert len(transport.calls) > calls

    def test_repository_cap_and_empty_account(self):
        repos = [
            {
                "name": f"repo-{index}", "private": False, "fork": False,
                "full_name": f"octocat/repo-{index}",
                "html_url": f"https://github.com/octocat/repo-{index}",
                "description": None, "topics": [],
            }
            for index in range(config.GITHUB_MAX_REPOS + 3)
        ]
        routes = _routes(repos=repos, readme="")
        for index in range(config.GITHUB_MAX_REPOS + 3):
            routes[f"https://api.github.com/repos/octocat/repo-{index}/languages"] = (200, {}, {})
            routes[f"https://api.github.com/repos/octocat/repo-{index}/readme"] = (404, {"message": "none"}, {})
        result = analyze_github("octocat", transport=FakeGitHub(routes), token="")
        assert len(result.repositories) == config.GITHUB_MAX_REPOS
        clear_github_cache()
        empty = analyze_github("octocat", transport=FakeGitHub(_routes(repos=[])), token="")
        assert empty.repositories == []
        assert any("No public non-fork" in warning for warning in empty.warnings)

    def test_transport_rejects_other_hosts(self):
        with pytest.raises(ValueError):
            UrllibTransport().request("https://example.com/users/octocat", {})
        with pytest.raises(ValueError):
            UrllibTransport().request("http://api.github.com/users/octocat", {})


class TestCareerReport:
    def test_projects_without_employment_are_not_invented(self):
        resume = analyze_text(PROJECTS_ONLY, "text")
        assert resume.status == STATUS_SUCCESS
        assert resume.experience == []
        assert resume.errors == []
        assert any("experience" in warning.lower() for warning in resume.warnings)
        report = career_report(resume)
        assert report.resume_status == STATUS_SUCCESS
        assert report.comparison is None
        assert report.github_status is None
        assert report.readiness.job_specific is False
        assert report.readiness.estimate is None
        assert "No job description" in report.readiness.summary
        assert report.recommendations.status == "unavailable"
        assert report.roadmap.status == "unavailable"
        assert any("not requested" in item for item in report.limitations)
        assert "ats" in report.readiness.disclaimer.lower()
        assert "not an ats" in report.readiness.disclaimer.lower() or "not a validated" in report.readiness.disclaimer.lower()

    def test_dated_employment_is_extracted(self):
        resume = analyze_text(EMPLOYED, "text")
        assert resume.experience
        assert resume.experience[0].start_date
        job = analyze_job("Requirements\n- 3+ years of professional experience\n- Python\n")
        report = career_report(resume, job, as_of=AS_OF)
        experience = next(item for item in report.comparison.matches if item.requirement.kind == "experience")
        python = next(item for item in report.comparison.matches if item.requirement.skill_name == "Python")
        assert experience.outcome == OUTCOME_MATCHED
        assert python.outcome == OUTCOME_MATCHED
        assert "Python" in report.recommendations.matched_skills
        assert report.recommendations.items == []

    def test_mentioned_skill_without_a_project_still_matches(self):
        resume = analyze_text(SKILLS_ONLY, "text")
        assert resume.projects == []
        python = next(skill for skill in resume.skills if skill.name == "Python")
        assert python.evidence_type == "mentioned"
        job = analyze_job("Requirements\n- Python\n")
        report = career_report(resume, job)
        match = report.comparison.matches[0]
        assert match.outcome == OUTCOME_MATCHED
        assert match.evidence
        assert "Python" not in _names(report)
        assert report.readiness.estimate == 100

    def test_python_only_match_and_miss(self):
        job = analyze_job("Requirements\n- Python\n")
        present = analyze_text(SKILLS_ONLY, "text")
        matched = career_report(present, job)
        assert matched.readiness.estimate == 100
        assert matched.readiness.band == "strong evidence"
        assert "1 matched and 0 unsatisfied" in matched.readiness.summary
        assert "contributes 1" in matched.readiness.summary
        assert matched.recommendations.items == []
        assert matched.roadmap.status == "unavailable"

        absent = analyze_text(PROJECTS_ONLY, "text")
        missing = career_report(absent, job)
        assert missing.comparison.matches[0].outcome == OUTCOME_MISSING
        assert missing.readiness.estimate == 0
        assert missing.readiness.band == "little evidence"
        assert _names(missing) == ["Python"]
        assert missing.recommendations.items[0].gap_kind == "missing_required"
        assert missing.recommendations.items[0].posting_text
        assert "http" not in missing.recommendations.items[0].practice_task
        assert "resume until" in missing.recommendations.items[0].practice_task
        assert [item.skill_name for item in missing.roadmap.milestones] == ["Python"]

    def test_frontend_gaps_recommendations_and_unverified_experience(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        job = analyze_job(FRONTEND_POSTING)
        report = career_report(resume, job, as_of=AS_OF)
        comparison = report.comparison
        assert comparison.missing_count > 0
        names = {item.requirement.skill_name: item for item in comparison.matches}
        assert names["TypeScript"].outcome == OUTCOME_MISSING
        assert names["Flux"].outcome == OUTCOME_MISSING
        assert names["REST API"].outcome == OUTCOME_MISSING
        assert all(item.outcome == OUTCOME_INDETERMINATE for item in comparison.matches if item.requirement.kind == "experience")

        recommended = _names(report)
        assert "JavaScript" not in recommended
        assert "React" not in recommended
        assert "Git" not in recommended
        assert "TypeScript" in recommended
        assert "REST API" in recommended
        assert any(item.startswith("Flux or Redux") for item in recommended)
        typescript = next(item for item in report.recommendations.items if item.skill_name == "TypeScript")
        gitlab = next(item for item in report.recommendations.items if item.skill_name == "GitLab")
        assert typescript.gap_kind == "missing_required"
        assert gitlab.gap_kind == "missing_preferred"
        assert gitlab.priority == PRIORITY_PREFERRED
        assert recommended.index("TypeScript") < recommended.index("GitLab")
        assert report.recommendations.experience_gaps
        assert all(item.gap_kind == "unverified_experience" for item in report.recommendations.experience_gaps)
        assert "professional experience" not in recommended

        scored = [item for item in report.readiness.criteria if item.scored]
        earned = sum(item.credit for item in scored)
        assert report.readiness.estimate == int(round(100 * earned / len(scored)))
        assert all(item.scored is False for item in report.readiness.criteria if item.status == "unverified")
        assert all(item.scored is False for item in report.readiness.criteria if item.priority == PRIORITY_PREFERRED)
        assert "hiring" in report.readiness.disclaimer.lower()
        blob = report.roadmap.to_json().lower()
        assert "http" not in blob
        assert "coursera" not in blob
        titles = [item.title for item in report.roadmap.milestones]
        assert any(title.startswith("Employment evidence") for title in titles)

    def test_unverified_experience_does_not_lower_a_matched_skill(self):
        resume = analyze_text(SKILLS_ONLY, "text")
        job = analyze_job("Requirements\n- Python\n- 5+ years of professional experience\n")
        report = career_report(resume, job, as_of=AS_OF)
        experience = next(item for item in report.comparison.matches if item.requirement.kind == "experience")
        assert experience.outcome == OUTCOME_INDETERMINATE
        assert report.readiness.estimate == 100
        assert report.recommendations.experience_gaps
        assert report.recommendations.items == []

    def test_preferred_and_related_are_not_treated_as_required_credit(self):
        resume = analyze_text(SKILLS_ONLY, "text")
        preferred = analyze_job("Requirements\n- Python\n\nPreferred\n- Docker\n")
        report = career_report(resume, preferred)
        assert report.readiness.estimate == 100
        assert any(item.skill_name == "Docker" and item.gap_kind == "missing_preferred" for item in report.recommendations.items)

        related_resume = analyze_text(
            SKILLS_ONLY + "\nTensorFlow is listed beside the other skills.\n",
            "text",
        )
        related_job = analyze_job("Requirements\n- PyTorch\n")
        related = career_report(related_resume, related_job)
        assert related.comparison.matches[0].outcome == "related"
        assert related.readiness.estimate == 0
        assert related.recommendations.items[0].gap_kind == "related"
        assert "TensorFlow" in (related.recommendations.items[0].evidence_note or "")

    def test_rubric_weight_is_the_configured_credit(self):
        resume = analyze_text(SKILLS_ONLY, "text")
        job = analyze_job("Requirements\n- Python\n")
        original = config.READINESS_MATCHED_CREDIT
        config.READINESS_MATCHED_CREDIT = 0.5
        try:
            report = career_report(resume, job)
        finally:
            config.READINESS_MATCHED_CREDIT = original
        assert report.readiness.estimate == 50

    def test_roadmap_orders_prerequisites_and_records_a_time_budget(self):
        bare = """
CASE EXAMPLE
case.example@example.com | Example City

EDUCATION
BS Computer Science, Example University (2018 - 2022)
Studied general computing and did not name a programming language.
"""
        resume = analyze_text(bare, "text")
        assert not any(skill.name in {"Python", "JavaScript"} for skill in resume.skills)
        job = analyze_job("Requirements\n- TypeScript\n- Django\n")
        report = career_report(resume, job, weekly_hours=6)
        titles = [item.skill_name for item in report.roadmap.milestones]
        assert titles.index("Python") < titles.index("Django")
        assert titles.index("JavaScript") < titles.index("TypeScript")
        python = next(item for item in report.roadmap.milestones if item.skill_name == "Python")
        assert python.kind == "prerequisite"
        assert "did not separately require" in python.objective or "Practice" in python.practice_task
        assert report.roadmap.planning_note
        assert "6" in report.roadmap.planning_note
        assert "No measured duration" in report.roadmap.planning_note
        assert "http" not in report.roadmap.to_json()

        unset = career_report(resume, job, weekly_hours=0)
        assert "not a positive" in unset.roadmap.planning_note

    def test_github_observation_does_not_change_the_estimate(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        job = analyze_job(FRONTEND_POSTING)
        plain = career_report(resume, job, as_of=AS_OF)
        github = GitHubAnalysis(
            status=STATUS_SUCCESS,
            username="octocat",
            skills=[GitHubSkillEvidence(
                skill_name="TypeScript", repository="demo",
                repository_url="https://github.com/octocat/demo",
                source_field="languages", text="TypeScript",
                note="Present in the repository language list. This is not a proficiency level.",
            )],
        )
        observed = career_report(resume, job, github, as_of=AS_OF)
        assert observed.readiness.estimate == plain.readiness.estimate
        assert observed.github_status == STATUS_SUCCESS
        assert any("does not change this estimate" in line for line in observed.readiness.github_observations)
        assert "TypeScript" in observed.recommendations.items[0].skill_name or any(
            item.skill_name == "TypeScript" for item in observed.recommendations.items
        )

    def test_optional_failures_keep_the_resume(self):
        resume = analyze_text(SKILLS_ONLY, "text")
        failed_github = GitHubAnalysis(status="failed", reason="The GitHub request timed out.", errors=["The GitHub request timed out."])
        empty_job = analyze_job("")
        report = career_report(resume, empty_job, failed_github)
        assert report.resume_status == STATUS_SUCCESS
        assert resume.skills
        assert report.comparison is not None
        assert report.comparison.status != STATUS_SUCCESS
        assert report.readiness.job_specific is False
        assert report.readiness.estimate is None
        assert report.github_status == "failed"
        assert any("unavailable" in item.lower() for item in report.limitations)
        assert "employability" not in report.comparison.to_json().lower()
        assert "score" not in report.comparison.to_json().lower()

    def test_or_group_is_not_recommended_when_one_alternative_is_shown(self):
        resume = analyze_text(
            SKILLS_ONLY + "\nPROJECTS\nStore | Redux\n- Stored state with Redux.\n",
            "text",
        )
        job = analyze_job("Requirements\n- Experience with Flux or Redux\n")
        report = career_report(resume, job)
        assert report.comparison.matches[0].outcome == OUTCOME_MATCHED
        assert report.comparison.matches[0].satisfied_by == "Redux"
        assert report.recommendations.items == []
        assert "Redux" in report.recommendations.matched_skills
        assert "Flux" not in report.recommendations.matched_skills

    def test_react_project_does_not_verify_years_or_change_the_denominator(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        assert resume.experience == []
        assert any(skill.name == "React" and skill.evidence for skill in resume.skills)
        job = analyze_job(
            "Requirements\n"
            "- 3 years of professional web development experience, including 2 years with React.\n"
            "- React\n"
            "- TypeScript\n"
        )
        report = career_report(resume, job, as_of=AS_OF)
        react = next(item for item in report.comparison.matches if item.requirement.skill_name == "React")
        assert react.outcome == OUTCOME_MATCHED
        assert "year" not in react.requirement.text.lower()
        durations = [item for item in report.comparison.matches if item.requirement.kind == "experience"]
        assert len(durations) == 2
        assert all(item.outcome == OUTCOME_INDETERMINATE for item in durations)
        assert all(item.outcome not in (OUTCOME_MATCHED, OUTCOME_MISSING) for item in durations)
        scored = [item for item in report.readiness.criteria if item.scored]
        assert all(item.kind != "experience" for item in scored)
        assert all(item.scored is False and item.status == "unverified" for item in report.readiness.criteria if item.kind == "experience")
        assert "The denominator is 2 required item(s)." in report.readiness.summary
        assert "2 unverified required item(s)" in report.readiness.summary
        assert report.readiness.estimate == 50
        assert all(item.gap_kind == "unverified_experience" for item in report.recommendations.experience_gaps)
        assert all("not counted as satisfied or failed" in item.reason for item in report.recommendations.experience_gaps)
        assert "proficiency" in " ".join(report.roadmap.limitations).lower()
        assert all("master" not in (item.objective or "").lower() for item in report.roadmap.milestones)

    def test_alternative_duplicates_are_counted_once(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        job = analyze_job(
            "Requirements\n"
            "- Redux\n"
            "- Flux\n"
            "- Redux or Flux\n"
            "- state management\n"
        )
        report = career_report(resume, job, as_of=AS_OF)
        skills = [item for item in report.comparison.matches if item.requirement.kind == "skill"]
        assert len(skills) == 1
        assert skills[0].outcome == OUTCOME_MISSING
        assert set(skills[0].requirement.alternatives) == {"Redux", "Flux", "state management"}
        recommended = _names(report)
        assert recommended.count("Redux") == 0
        assert sum("Redux" in name and "Flux" in name for name in recommended) == 1
        scored = [item for item in report.readiness.criteria if item.scored]
        assert len(scored) == 1
        assert report.readiness.estimate == 0
        titles = [item.skill_name for item in report.roadmap.milestones if item.kind != "unverified_experience"]
        assert sum("Redux" in (title or "") for title in titles) == 1

    def test_roadmap_uses_frontend_foundations_before_later_tools(self):
        resume = analyze_text(FRONTEND_RESUME, "text")
        assert any(skill.name == "JavaScript" for skill in resume.skills)
        assert any(skill.name == "React" for skill in resume.skills)
        job = analyze_job(
            "Requirements\n"
            "- JavaScript and TypeScript\n"
            "- Understanding of functional programming principles\n"
            "- Experience with React hooks\n"
            "- Redux\n"
            "- Flux\n"
            "- Redux or Flux\n"
            "- Experience consuming REST APIs\n"
            "- testing, build automation, and CI/CD\n"
            "\n"
            "Preferred\n"
            "- Docker\n"
            "- Linux\n"
            "- Bash\n"
        )
        report = career_report(resume, job, as_of=AS_OF)
        titles = [item.skill_name for item in report.roadmap.milestones]
        assert "JavaScript" not in titles
        assert "React" not in titles
        state = next(title for title in titles if "Redux" in title and "Flux" in title)
        order = [
            "functional programming", "TypeScript", "React hooks", state,
            "REST API", "testing", "build automation", "CI/CD", "Docker", "Linux", "Bash",
        ]
        positions = [titles.index(name) for name in order]
        assert positions == sorted(positions)
        assert all("master" not in (item.objective or "").lower() for item in report.roadmap.milestones)
        assert all("until" in item.practice_task.lower() for item in report.recommendations.items)
        assert "http" not in report.roadmap.to_json().lower()


WEBFLOW_POSTING = """
Front-End Developer

This role builds marketing pages with JavaScript, HTML5, CSS3, and Webflow.
Designers review the pages in the browser.
"""

WEBFLOW_RESUME = """
ALEX EXAMPLE
alex.example@example.com

TECHNICAL SKILLS
JavaScript, HTML, CSS
"""


class TestUnlabeledPosting:
    def test_webflow_gap_without_a_required_heading(self):
        resume = analyze_text(WEBFLOW_RESUME, "text")
        assert {skill.name for skill in resume.skills} >= {"JavaScript", "HTML", "CSS"}
        assert not any(skill.name == "Webflow" for skill in resume.skills)
        job = analyze_job(WEBFLOW_POSTING)
        assert any("headings" in warning.lower() for warning in job.warnings)
        skills = [item for item in job.requirements if item.kind == "skill"]
        assert {item.skill_name for item in skills} == {"JavaScript", "HTML", "CSS", "Webflow"}
        assert all(item.priority == PRIORITY_UNSPECIFIED for item in skills)
        assert all(item.priority != PRIORITY_REQUIRED for item in job.requirements)

        report = career_report(resume, job, as_of=AS_OF, weekly_hours=4)
        outcomes = {item.requirement.skill_name: item for item in report.comparison.matches}
        assert outcomes["JavaScript"].outcome == OUTCOME_MATCHED
        assert outcomes["HTML"].outcome == OUTCOME_MATCHED
        assert outcomes["CSS"].outcome == OUTCOME_MATCHED
        assert outcomes["Webflow"].outcome == OUTCOME_MISSING
        assert outcomes["Webflow"].evidence == []
        assert "Webflow" in outcomes["Webflow"].requirement.text

        assert report.readiness.estimate is None
        assert report.readiness.job_specific is True
        assert "did not label any requirement as required" in report.readiness.summary
        assert "The denominator is 0 required item(s)." in report.readiness.summary
        assert all(item.scored is False for item in report.readiness.criteria)
        assert any(
            item.name == "Webflow" and item.priority == PRIORITY_UNSPECIFIED and item.status == "missing"
            for item in report.readiness.criteria
        )

        assert [item.skill_name for item in report.recommendations.items] == ["Webflow"]
        gap = report.recommendations.items[0]
        assert gap.gap_kind == "missing_unspecified"
        assert gap.priority == PRIORITY_UNSPECIFIED
        assert "required or preferred" in gap.reason
        assert "until" in gap.practice_task
        assert "JavaScript" not in _names(report)
        assert "HTML" not in _names(report)
        assert "CSS" not in _names(report)

        titles = [item.skill_name for item in report.roadmap.milestones]
        assert titles == ["Webflow"]
        assert report.roadmap.milestones[0].kind == "missing_unspecified"
        assert "4" in report.roadmap.planning_note
        assert "No measured duration" in report.roadmap.planning_note
        assert "guarantee" not in (report.roadmap.planning_note or "").lower()
        assert "http" not in report.roadmap.to_json()

        github = GitHubAnalysis(
            status=STATUS_SUCCESS,
            username="octocat",
            public_repos=12,
            skills=[GitHubSkillEvidence(
                skill_name="Webflow", repository="demo",
                repository_url="https://github.com/octocat/demo",
                source_field="languages", text="Webflow",
                note="Present in the repository language list. This is not a proficiency level.",
            )],
        )
        observed = career_report(resume, job, github, as_of=AS_OF)
        assert observed.readiness.estimate is None
        assert observed.comparison.matches[-1].requirement.skill_name == "Webflow" or any(
            item.requirement.skill_name == "Webflow" and item.outcome == OUTCOME_MISSING
            for item in observed.comparison.matches
        )
        webflow = next(item for item in observed.comparison.matches if item.requirement.skill_name == "Webflow")
        assert webflow.outcome == OUTCOME_MISSING
        assert webflow.evidence == []
        assert any("does not change this estimate" in line for line in observed.readiness.github_observations)
        assert "12" not in " ".join(observed.readiness.github_observations)

    def test_the_same_skills_stay_required_under_a_requirements_heading(self):
        resume = analyze_text(WEBFLOW_RESUME, "text")
        job = analyze_job(
            "Requirements\n- JavaScript, HTML5, CSS3, and Webflow\n"
        )
        assert all(item.priority == PRIORITY_REQUIRED for item in job.requirements if item.kind == "skill")
        report = career_report(resume, job, as_of=AS_OF)
        assert report.readiness.estimate == 75
        assert "The denominator is 4 required item(s)." in report.readiness.summary
        assert report.recommendations.items[0].skill_name == "Webflow"
        assert report.recommendations.items[0].gap_kind == "missing_required"

    def test_unlabeled_react_years_stay_unverified_when_only_a_project_exists(self):
        resume = analyze_text(
            "ALEX EXAMPLE\nalex.example@example.com\n\n"
            "PROJECTS\nPuzzle | React.js\n- Interactive puzzle built with React.\n",
            "text",
        )
        assert any(skill.name == "React" and skill.evidence for skill in resume.skills)
        assert resume.experience == []
        job = analyze_job("Front-End Developer\n\nThis role needs 3 years with React.\n")
        assert any("headings" in warning.lower() for warning in job.warnings)
        report = career_report(resume, job, as_of=AS_OF)
        experience = next(item for item in report.comparison.matches if item.requirement.kind == "experience")
        assert experience.requirement.priority == PRIORITY_UNSPECIFIED
        assert experience.requirement.experience_focus == "React"
        assert experience.requirement.years_min == 3
        assert experience.outcome == OUTCOME_INDETERMINATE
        assert experience.support == []
        assert "unverif" in (experience.note or "").lower()
        react = next(item for item in report.comparison.matches if item.requirement.skill_name == "React")
        assert react.outcome == OUTCOME_MATCHED
        assert "year" not in (react.requirement.text or "").lower()
        assert report.readiness.estimate is None
        assert all(item.scored is False for item in report.readiness.criteria if item.kind == "experience")
        assert "The denominator is 0 required item(s)." in report.readiness.summary
        assert report.recommendations.experience_gaps
        assert report.recommendations.experience_gaps[0].gap_kind == "unverified_experience"
        assert report.recommendations.experience_gaps[0].skill_name == "React"
        assert "not counted as satisfied or failed" in report.recommendations.experience_gaps[0].reason
        assert "React" not in _names(report)
