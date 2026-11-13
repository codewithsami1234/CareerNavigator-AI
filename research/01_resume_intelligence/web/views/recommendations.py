"""Recommendations produced by the existing gap module."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.recommendation_card import render_recommendation_cards
from web.components.workflow import build_career
from web.ui.session_state import stored_weekly_hours
from web.view_model import has_structured_result, recommendation_lines


def render() -> None:
    page_header(
        "Recommendations",
        "Items come from the comparison. No course provider, certificate, or external link is added.",
    )
    st.caption("Do not add a skill to a resume until the work exists.")
    analysis = st.session_state.get("analysis")
    if analysis is None or not has_structured_result(analysis):
        st.info("Analyze a resume, then compare a job description, to see role-specific gaps.")
        return
    report = build_career(analysis, stored_weekly_hours())
    lines = recommendation_lines(report.recommendations)
    if report.recommendations.status != "success":
        st.caption(lines[0])
        return
    render_recommendation_cards(lines)
    if report.recommendations.limitations:
        for note in report.recommendations.limitations:
            st.caption(note)
