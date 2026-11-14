"""CareerNavigator AI local web app.

Launch from ``research/01_resume_intelligence``:

    python -m streamlit run web/app.py --server.address 127.0.0.1 --server.port 8501

View modules live in ``web/views`` so Streamlit does not treat them as automatic pages.
"""
from __future__ import annotations

import sys
from pathlib import Path

_PACKAGE = str(Path(__file__).resolve().parents[1])
while _PACKAGE in sys.path:
    sys.path.remove(_PACKAGE)
sys.path.insert(0, _PACKAGE)

import streamlit as st

from web.components.sidebar import render_sidebar
from web.ui.session_state import init_state
from web.views import (
    career_assessment,
    career_roadmap,
    dashboard,
    github_analysis,
    history,
    job_analyzer,
    recommendations,
    reports,
    resume_analyzer,
    settings,
    skills_intelligence,
)

_VIEWS = {
    "Overview": dashboard.render,
    "Resume Intelligence": resume_analyzer.render,
    "Job Analyzer": job_analyzer.render,
    "Skills Intelligence": skills_intelligence.render,
    "Career Assessment": career_assessment.render,
    "GitHub Intelligence": github_analysis.render,
    "Recommendations": recommendations.render,
    "Career Roadmap": career_roadmap.render,
    "Reports": reports.render,
    "Analysis History": history.render,
    "Settings": settings.render,
}


def _inject_css() -> None:
    styles = Path(__file__).resolve().parent / "styles"
    chunks = []
    for name in ("main.css", "components.css"):
        path = styles / name
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8"))
    if chunks:
        st.markdown(f"<style>{''.join(chunks)}</style>", unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="CareerNavigator AI",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    _inject_css()
    init_state()
    page = render_sidebar()
    _VIEWS.get(page, dashboard.render)()


main()
