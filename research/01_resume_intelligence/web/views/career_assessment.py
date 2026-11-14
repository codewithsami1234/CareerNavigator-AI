"""Rule-based readiness. The scoring formula is not changed here."""
from __future__ import annotations

import streamlit as st

import config
from web.components.header import page_header
from web.components.workflow import render_career
from web.view_model import has_structured_result


def render() -> None:
    page_header(
        "Career Assessment",
        "This is a rule-based evidence estimate, not a hiring prediction or validated ATS score.",
    )
    st.write(
        "The estimate uses the existing rubric. "
        f"A matched required item contributes {config.READINESS_MATCHED_CREDIT:g}. "
        f"A related or missing required item contributes {config.READINESS_UNSATISFIED_CREDIT:g}. "
        "Preferred items, unspecified items, and unverified durations stay out of the denominator. "
        "Public GitHub observations do not change the number. "
        "This is a rule-based estimate, not a validated hiring prediction and not an ATS score."
    )
    analysis = st.session_state.get("analysis")
    if analysis is None or not has_structured_result(analysis):
        st.info("Analyze a resume before readiness can be calculated.")
        return
    render_career(analysis)
