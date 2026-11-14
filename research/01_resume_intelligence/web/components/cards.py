"""Small status summaries. Counts come from the stored analysis only."""
from __future__ import annotations

import streamlit as st

from web.components.empty_state import empty_state
from web.view_model import detected_section_names, has_structured_result


def render_history() -> None:
    history = list(st.session_state.get("history") or [])
    if not history:
        st.caption("No analysis has been run in this session.")
        return
    st.caption("Recent analyses in this session")
    for item in reversed(history):
        st.text(f"{item['file_name']} · {item['status']} · {item['skills']} skill(s)")


def render_overview_metrics(analysis) -> None:
    if analysis is None or not has_structured_result(analysis):
        return
    sections = detected_section_names(analysis)
    columns = st.columns(4)
    columns[0].metric("Status", analysis.status)
    columns[1].metric("Skills", len(analysis.skills))
    columns[2].metric("Sections", len(sections))
    columns[3].metric("Text length", analysis.text_length)


def render_live_metrics() -> None:
    """Session figures. Matched and missing stay blank until a comparison exists."""
    analysis = st.session_state.get("analysis")
    report = st.session_state.get("job_report")
    if analysis is None or not has_structured_result(analysis):
        empty_state(
            "No analysis figures yet",
            "Upload a resume to see extracted skills. Matched and missing skills appear after a job comparison.",
        )
        return
    matched = "Not compared"
    missing = "Not compared"
    if report is not None:
        matched = str(getattr(report, "matched_count", 0))
        missing = str(getattr(report, "missing_count", 0))
    columns = st.columns(4)
    columns[0].metric("Resume status", analysis.status)
    columns[1].metric("Extracted skills", len(analysis.skills))
    columns[2].metric("Matched skills", matched)
    columns[3].metric("Missing skills", missing)


def render_quick_actions() -> None:
    st.caption("Open a focused workspace. The current session stays in place.")
    actions = (
        ("Resume Intelligence", "Resume workspace"),
        ("Job Analyzer", "Job workspace"),
        ("Skills Intelligence", "Skills workspace"),
        ("Reports", "Report workspace"),
    )
    columns = st.columns(4)
    for column, (page, label) in zip(columns, actions):
        if column.button(label, key=f"goto-{page}"):
            st.session_state["nav_page"] = page
            st.rerun()


def render_workflow_status() -> None:
    analysis = st.session_state.get("analysis")
    job = st.session_state.get("job_analysis")
    github = st.session_state.get("github_analysis")
    career = st.session_state.get("career_report")
    resume_state = "not analyzed yet" if analysis is None else analysis.status
    job_state = "not compared" if job is None else job.status
    github_state = "not requested" if github is None else github.status
    if career is None or career.readiness.estimate is None:
        ready = "no numeric estimate"
    else:
        ready = f"{career.readiness.estimate} / 100"
    st.caption(
        f"Session · resume {resume_state} · job {job_state} · GitHub {github_state} · readiness {ready}."
    )
