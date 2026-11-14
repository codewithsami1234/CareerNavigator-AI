"""One session report assembled from stored pipeline objects."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.workflow import build_career, render_downloads, show_lines
from web.ui.session_state import stored_weekly_hours
from web.view_model import (
    github_profile_lines, has_structured_result, readiness_lines, recommendation_lines, roadmap_lines,
    skill_rows,
)


def render() -> None:
    page_header("Reports", "This page repeats stored results. It does not create a new score.")
    analysis = st.session_state.get("analysis")
    if analysis is None:
        st.info("Analyze a resume before a report can be downloaded.")
        return
    with st.container(border=True):
        st.markdown("**Resume**")
        st.text(f"File: {analysis.file_name or 'resume'} · status {analysis.status}")
        if has_structured_result(analysis):
            for name, category, evidence, mentions in skill_rows(analysis):
                st.text(f"{name} · {category} · {evidence} · {mentions} mention(s)")
    if has_structured_result(analysis):
        report = build_career(analysis, stored_weekly_hours())
        with st.container(border=True):
            st.markdown("**Readiness**")
            show_lines(readiness_lines(report.readiness))
        with st.container(border=True):
            st.markdown("**Recommendations**")
            show_lines(recommendation_lines(report.recommendations))
        with st.container(border=True):
            st.markdown("**Roadmap**")
            show_lines(roadmap_lines(report.roadmap))
    github = st.session_state.get("github_analysis")
    with st.container(border=True):
        st.markdown("**GitHub**")
        if github is None:
            st.caption("No GitHub profile has been requested. Resume and job analysis do not need one.")
        else:
            show_lines(github_profile_lines(github))
    st.caption("JSON and CSV downloads use the stored objects. A PDF export is not included.")
    render_downloads()
