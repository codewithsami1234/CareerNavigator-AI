"""Public GitHub metadata. Source code is not downloaded or executed."""
from __future__ import annotations

import streamlit as st

from web.components.header import page_header
from web.components.workflow import render_github


def render() -> None:
    page_header(
        "GitHub Intelligence",
        "Public profile and repository metadata only. Source code is not reviewed.",
    )
    st.caption(
        "Future checks such as placeholder-repository detection and source-code review are not available. "
        "An empty or private profile is not evidence of low ability. "
        "These observations are separate from resume-verified skills."
    )
    render_github()
