"""One sidebar for every view. The first item is the full workflow."""
from __future__ import annotations

import streamlit as st

from web.ui.session_state import reset_session

PAGES = (
    "Overview",
    "Resume Intelligence",
    "Job Analyzer",
    "Skills Intelligence",
    "Career Assessment",
    "Recommendations",
    "Career Roadmap",
    "GitHub Intelligence",
    "Reports",
    "Analysis History",
    "Settings",
)

_MARK = (
    "<svg width='22' height='22' viewBox='0 0 22 22' fill='none' aria-hidden='true'>"
    "<path d='M11 3.2l1.7 4.6 4.8.4-3.7 3.1 1.2 4.7L11 13.6 6.9 16l1.2-4.7L4.5 8.2l4.8-.4L11 3.2z' "
    "fill='white'/></svg>"
)


def render_sidebar() -> str:
    st.sidebar.markdown(
        "<div class='cn-brand'>"
        f"<div class='cn-mark'>{_MARK}</div>"
        "<div><strong>CareerNavigator AI</strong>"
        "<span>Career Intelligence Platform</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    page = st.sidebar.radio("Pages", PAGES, key="nav_page", label_visibility="collapsed")
    st.sidebar.caption(
        "The resume is not sent to an external service. "
        "GitHub, when you ask for it, uses the public GitHub API only. "
        "Repository source code is not analyzed. "
        "Job listings are not scraped. "
        "Readiness is not a hiring prediction and not an ATS score."
    )
    analysis = st.session_state.get("analysis")
    if analysis is None:
        st.sidebar.caption("Resume: not analyzed yet.")
    else:
        st.sidebar.caption(f"Resume: {analysis.status}.")
    if st.session_state.get("job_report") is None:
        st.sidebar.caption("Job comparison: not run.")
    else:
        st.sidebar.caption("Job comparison: stored for this session.")
    if st.session_state.get("github_analysis") is None:
        st.sidebar.caption("GitHub: not requested.")
    else:
        st.sidebar.caption(f"GitHub: {st.session_state['github_analysis'].status}.")
    st.sidebar.markdown(
        "<div class='cn-user'><div class='cn-avatar'>CN</div>"
        "<div><strong>Local session</strong>"
        "<span>Streamlit session. The React app has accounts.</span></div></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Version 1.0 · local pipeline")
    st.sidebar.button("Reset session", on_click=reset_session)
    return page
