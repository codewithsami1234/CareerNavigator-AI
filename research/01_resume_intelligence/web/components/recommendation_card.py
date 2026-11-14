"""Present pipeline lines without rewriting them."""
from __future__ import annotations

import streamlit as st


def _is_milestone(line: str) -> bool:
    head, dot, _rest = line.partition(". ")
    return bool(dot) and head.isdigit()


def render_recommendation_cards(lines: list[str]) -> None:
    """A middle-dot line starts a card. The text stays the pipeline wording."""
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if " · " in line and current:
            groups.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        groups.append(current)
    for group in groups:
        with st.container(border=True):
            for line in group:
                st.text(line)


def render_roadmap_cards(lines: list[str]) -> None:
    intro: list[str] = []
    groups: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _is_milestone(line):
            if current:
                groups.append(current)
            current = [line]
        elif current:
            current.append(line)
        else:
            intro.append(line)
    if current:
        groups.append(current)
    for line in intro:
        st.caption(line)
    for group in groups:
        with st.container(border=True):
            st.markdown("<p class='cn-mile'>Milestone</p>", unsafe_allow_html=True)
            for line in group:
                st.text(line)
