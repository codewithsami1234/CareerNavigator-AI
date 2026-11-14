"""Pasted or uploaded job descriptions. No job-board collection."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.workflow import render_job


def render() -> None:
    page_header(
        "Job Analyzer",
        "Read one posting on this computer. Job boards are not searched.",
    )
    st.caption(
        "Paste the posting, or upload a PDF, DOCX, or TXT file. OCR is not run on job files."
    )
    analysis = st.session_state.get("analysis")
    if analysis is None:
        st.subheader("Job description")
        st.caption("Analyze a resume first. The comparison is shown under that result.")
        return
    render_job(analysis)
