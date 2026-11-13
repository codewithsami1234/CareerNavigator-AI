"""Skill evidence and comparison outcomes from the stored result."""
from __future__ import annotations

import streamlit as st

from web.components.charts import skill_category_chart
from web.components.header import page_header
from web.components.workflow import render_job_result
from web.view_model import has_structured_result, skill_rows


def render() -> None:
    page_header(
        "Skills Intelligence",
        "Matched, missing, related, and unverified outcomes come from the comparison.",
    )
    st.caption("Related skills are not matches. Proficiency is not inferred.")
    analysis = st.session_state.get("analysis")
    if analysis is None or not has_structured_result(analysis):
        st.info("Analyze a resume before reviewing skills.")
        return
    rows = skill_rows(analysis)
    if not rows:
        st.caption("No skills were returned.")
    else:
        for name, category, evidence, mentions in rows:
            st.text(f"{name} · {category} · {evidence} · {mentions} mention(s)")
    skill_category_chart(analysis)
    job = st.session_state.get("job_analysis")
    report = st.session_state.get("job_report")
    if job is None or report is None:
        st.info("Compare a job description to see matched, missing, related, and unverified requirements.")
        return
    total = len(getattr(report, "matches", []) or [])
    if total:
        matched = int(getattr(report, "matched_count", 0))
        st.caption(
            f"Matched {matched} of {total} requirements. "
            "Related, missing, and unverified requirements stay in their own groups."
        )
        st.progress(matched / total)
    render_job_result(job, report)
