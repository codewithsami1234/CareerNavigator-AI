"""Quiet placeholder when a result has not been calculated."""
from __future__ import annotations

import html

import streamlit as st


def empty_state(title: str, body: str) -> None:
    st.markdown(
        "<div class='cn-empty'>"
        f"<strong>{html.escape(title)}</strong>"
        f"<p>{html.escape(body)}</p>"
        "</div>",
        unsafe_allow_html=True,
    )
