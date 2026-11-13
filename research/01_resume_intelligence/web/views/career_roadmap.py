"""Ordered milestones from the existing roadmap. No durations are invented."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.recommendation_card import render_roadmap_cards
from web.components.workflow import build_career
from web.ui.session_state import stored_weekly_hours
from web.view_model import has_structured_result, roadmap_lines


def render() -> None:
    page_header(
        "Career Roadmap",
        "The sequence follows the pipeline roadmap. No course provider or completion date is added.",
    )
    st.caption(
        "Set optional weekly hours on Overview or Career Assessment. "
        "A weekly budget is not a completion date."
    )
    analysis = st.session_state.get("analysis")
    if analysis is None or not has_structured_result(analysis):
        st.info("Analyze a resume and compare a job description before a roadmap can be built.")
        return
    report = build_career(analysis, stored_weekly_hours())
    _render_guidance(report)
    lines = roadmap_lines(report.roadmap)
    if report.roadmap.status != "success":
        st.caption(lines[0])
        return
    render_roadmap_cards(lines)
    if report.roadmap.limitations:
        for note in report.roadmap.limitations:
            st.caption(note)


def _render_guidance(report) -> None:
    """Show path labels and horizons already attached to the career report."""
    guidance = getattr(report, "guidance", None)
    if guidance is None:
        return
    if getattr(guidance, "status", None) != "success":
        if getattr(guidance, "reason", None):
            st.caption(guidance.reason)
        return
    st.subheader("Evidence-based guidance")
    st.caption("These notes do not change the readiness estimate. Career-path labels are not job offers.")
    for item in guidance.career_paths:
        st.markdown(f"**{item.title}.** {item.reason}")
    for title, rows in (
        ("Near-term", guidance.short_term),
        ("Later", guidance.long_term),
        ("Focus slots", guidance.weekly_focus),
        ("Skills to strengthen", guidance.skills_to_strengthen),
        ("Project ideas", guidance.project_ideas),
    ):
        if not rows:
            continue
        st.markdown(f"**{title}**")
        for item in rows:
            st.markdown(f"- {item.title}: {item.reason}")
    for note in guidance.github_notes:
        st.caption(note)
