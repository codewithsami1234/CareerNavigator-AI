"""Session keys shared by every view. Navigation does not clear an analysis."""
from __future__ import annotations

import streamlit as st

DEFAULTS = {
    "upload_generation": 0,
    "analysis": None,
    "job_analysis": None,
    "job_report": None,
    "github_analysis": None,
    "use_ocr": False,
    "history": [],
    "career_report": None,
}


def init_state() -> None:
    for key, value in DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = value if not isinstance(value, list) else []


def reset_session() -> None:
    """Start a new upload. History from this session is cleared with the result."""
    st.session_state["upload_generation"] = st.session_state.get("upload_generation", 0) + 1
    st.session_state["analysis"] = None
    st.session_state["job_analysis"] = None
    st.session_state["job_report"] = None
    st.session_state["github_analysis"] = None
    st.session_state["use_ocr"] = False
    st.session_state["history"] = []
    st.session_state["career_report"] = None


def remember_analysis(analysis) -> None:
    history = list(st.session_state.get("history") or [])
    history.append({
        "file_name": analysis.file_name or "resume",
        "status": analysis.status,
        "skills": len(analysis.skills),
    })
    st.session_state["history"] = history[-8:]


def weekly_hours_key() -> str:
    return f"weekly-hours-{st.session_state['upload_generation']}"


def stored_weekly_hours() -> int | None:
    raw = st.session_state.get(weekly_hours_key(), 0)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    hours = int(raw)
    return hours if hours > 0 else None
