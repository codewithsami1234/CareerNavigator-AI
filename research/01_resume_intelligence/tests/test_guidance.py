"""Guidance explains existing evidence. It does not change the readiness estimate."""
from datetime import date

from pipeline import analyze_job, analyze_text, career_report
from schemas import ResumeAnalysis, STATUS_FAILED, STATUS_SUCCESS


RESUME = """
Alex Example
alex.example@example.com

Skills
React, Docker

Experience
Software Intern at Example Labs (Jan 2024 - Jun 2024)
- Built services with Python and Django
"""

JOB = """
Required qualifications
- Python
- Kubernetes
- SQL

Preferred qualifications
- React
"""


def _report():
    resume = analyze_text(RESUME)
    job = analyze_job(JOB)
    return resume, job, career_report(resume, job, weekly_hours=5, as_of=date(2026, 6, 1))


class TestGuidance:
    def test_partial_support_and_paths_do_not_change_the_estimate(self):
        resume, _job, report = _report()
        assert resume.status == STATUS_SUCCESS
        outcomes = {item.requirement.skill_name: item.outcome for item in report.comparison.matches}
        assert outcomes["Python"] == "matched"
        assert outcomes["Kubernetes"] == "related"
        assert outcomes["SQL"] == "missing"
        assert outcomes["React"] == "matched"
        guidance = report.guidance
        assert guidance.status == STATUS_SUCCESS
        partial = {item.title: item.reason for item in guidance.partially_supported}
        assert "partial support" in partial["React"]
        assert "still counts as a match" in partial["React"]
        assert "do not earn readiness credit" in partial["Kubernetes"]
        strengthen = {item.title for item in guidance.skills_to_strengthen}
        assert strengthen == {"React"}
        assert "Python" not in strengthen
        paths = [item.title for item in guidance.career_paths]
        assert paths[0] == "Software engineering"
        assert "Web development" in paths
        assert "Cloud and DevOps" not in paths
        assert all("not a job offer" in item.reason for item in guidance.career_paths)
        assert any(item.title == "SQL" for item in guidance.project_ideas)
        assert any(item.title == "SQL" for item in guidance.short_term)
        assert guidance.weekly_focus[0].title == guidance.short_term[0].title
        assert "not an estimate" in guidance.weekly_focus[0].reason
        assert report.readiness.estimate == 33
        assert "guidance" in report.to_dict()

    def test_failed_resume_and_missing_hours_add_nothing(self):
        failed = career_report(ResumeAnalysis(status=STATUS_FAILED, errors=["bad"]))
        assert failed.guidance.status == "unavailable"
        assert failed.guidance.career_paths == []
        assert failed.guidance.skills_to_strengthen == []
        resume = analyze_text(RESUME)
        plain = career_report(resume, analyze_job(JOB))
        assert plain.guidance.weekly_focus == []
        assert any("weekly hour budget" in note for note in plain.guidance.limitations)
        assert plain.readiness.estimate == 33

    def test_github_names_stay_out_of_the_path(self):
        class Skill:
            skill_name = "Rust"

        class GitHub:
            status = STATUS_SUCCESS
            skills = [Skill()]

        resume = analyze_text(RESUME)
        report = career_report(resume, analyze_job(JOB), GitHub(), as_of=date(2026, 6, 1))
        assert report.guidance.github_notes
        assert "Rust" in report.guidance.github_notes[0]
        assert "not resume evidence" in report.guidance.github_notes[0]
        assert all("Rust" not in item.reason for item in report.guidance.career_paths)
        assert report.readiness.estimate == 33
