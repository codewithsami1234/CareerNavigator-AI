"""Local limits. This Streamlit page does not sign in."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.ui.formatters import taxonomy_summary
from web.ui.session_state import reset_session


def render() -> None:
    page_header(
        "Settings",
        "This Streamlit page does not sign in. The React workspace has accounts.",
    )
    st.markdown("**Document reading**")
    st.write(
        "PDF, DOCX, and TXT use the local pipeline. "
        "Scanned PDFs can use OpenCV preprocessing and Tesseract OCR when OCR is turned on. "
        "A low Tesseract confidence is a warning, not proof the text is correct."
    )
    st.markdown("**What stays out of scope**")
    st.write(
        "The app does not scrape job boards, download repository source code, or predict hiring. "
        "Readiness remains the existing rule-based estimate, not an ATS score."
    )
    summary = taxonomy_summary()
    if summary:
        st.caption(summary)
    st.button("Reset session", on_click=reset_session, key="settings-reset")
