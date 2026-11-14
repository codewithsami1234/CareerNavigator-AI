"""Session list of completed resume reads. Skill names are not kept here."""
from __future__ import annotations

import streamlit as st

from web.components.cards import render_history
from web.components.header import page_header


def render() -> None:
    page_header(
        "Analysis History",
        "Resumes read in this browser session. This list keeps the file name, status, and skill count only.",
    )
    render_history()
    st.caption("A new upload clears the list so an earlier resume cannot remain on screen.")
