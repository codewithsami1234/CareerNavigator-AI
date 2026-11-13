"""Page title row. Names come only from a parsed resume."""
from __future__ import annotations

import html
from datetime import datetime

import streamlit as st


def page_header(title: str, description: str) -> None:
    st.markdown("<p class='cn-kicker'>CareerNavigator AI</p>", unsafe_allow_html=True)
    st.title(title)
    st.caption(description)


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        hello = "Good morning"
    elif hour < 17:
        hello = "Good afternoon"
    else:
        hello = "Good evening"
    analysis = st.session_state.get("analysis")
    contact = getattr(analysis, "contact", None) if analysis is not None else None
    name = (getattr(contact, "name", None) or "").strip()
    if name:
        return f"{hello}, {name}"
    return hello


def render_topbar() -> None:
    analysis = st.session_state.get("analysis")
    if analysis is None:
        status = "Ready for a resume"
    else:
        status = f"Resume {analysis.status}"
    left, right = st.columns([4, 2])
    with left:
        st.markdown(
            f"<p class='cn-hello'>{html.escape(_greeting())}</p>",
            unsafe_allow_html=True,
        )
        st.caption(datetime.now().strftime("%A, %d %B %Y"))
    with right:
        st.markdown(
            f"<div class='cn-pill'><span class='cn-dot'></span>{html.escape(status)}</div>",
            unsafe_allow_html=True,
        )
