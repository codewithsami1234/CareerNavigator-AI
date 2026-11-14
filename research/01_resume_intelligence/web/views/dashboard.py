"""Overview plus the full local workflow."""
from __future__ import annotations

import streamlit as st

from web.components.cards import render_history, render_live_metrics, render_quick_actions, render_workflow_status
from web.components.header import render_topbar
from web.components.hero_card import render_hero
from web.components.workflow import INTRO, render_full_workflow
from web.ui.formatters import taxonomy_summary


def render() -> None:
    render_topbar()
    render_hero()
    st.write(INTRO)
    summary = taxonomy_summary()
    if summary:
        st.caption(summary)
    with st.container(border=True):
        st.markdown("<p class='cn-section'>Start here</p>", unsafe_allow_html=True)
        st.markdown(
            "1. Upload a PDF, DOCX, or TXT resume and analyze it on this computer.\n"
            "2. Review contact, skills, education, experience, projects, and certifications.\n"
            "3. Paste or upload one job description. Listings are not collected automatically.\n"
            "4. Compare requirements with resume evidence.\n"
            "5. Read the readiness estimate, recommendations, and roadmap.\n"
            "6. Optionally read a public GitHub profile.\n"
            "7. Download the JSON or CSV report from this session."
        )
    render_live_metrics()
    render_workflow_status()
    render_history()
    render_quick_actions()
    render_full_workflow()
