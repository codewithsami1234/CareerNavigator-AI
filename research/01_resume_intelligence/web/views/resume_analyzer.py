"""Resume upload and extracted fields."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.workflow import render_analysis, render_downloads, render_upload_controls
from web.view_model import has_structured_result


def render() -> None:
    page_header(
        "Resume Intelligence",
        "Extract meaningful career information from your resume.",
    )
    st.caption(
        "PDF, DOCX, and TXT files use the local pipeline. "
        "OCR runs only when you turn it on for a PDF, and only with a local Tesseract install. "
        "The upload is deleted after reading."
    )
    render_upload_controls()
    analysis = st.session_state.get("analysis")
    if analysis is None:
        st.info("Upload a resume to begin. Nothing has been analyzed yet.")
        return
    render_analysis(analysis)
    if has_structured_result(analysis):
        render_downloads()
