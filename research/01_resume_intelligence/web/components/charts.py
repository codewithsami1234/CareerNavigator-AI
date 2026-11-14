"""Charts from stored results. A chart is skipped when there is nothing to plot."""
from __future__ import annotations

import streamlit as st

from web.view_model import comparison_groups, skill_rows


def _bar(labels, values, x_name: str, y_name: str) -> None:
    if not labels:
        return
    try:
        import pandas as pd

        frame = pd.DataFrame({x_name: labels, y_name: values})
        st.bar_chart(frame, x=x_name, y=y_name)
    except Exception:
        st.caption("A chart could not be drawn. The lists above are unchanged.")


def skill_category_chart(analysis) -> None:
    counts = {}
    for _name, category, _kind, _mentions in skill_rows(analysis):
        if category:
            counts[category] = counts.get(category, 0) + 1
    if not counts:
        st.caption("No skill categories were returned, so no coverage chart was drawn.")
        return
    st.caption("Skill counts by taxonomy category. This is not a proficiency chart.")
    _bar(list(counts), list(counts.values()), "category", "skills")


def outcome_chart(report) -> None:
    if report is None or not getattr(report, "matches", None):
        return
    labels = []
    values = []
    for _outcome, heading, rows in comparison_groups(report):
        labels.append(heading)
        values.append(len(rows))
    if not any(values):
        return
    st.caption("Requirement counts by comparison outcome. Related is not a match.")
    _bar(labels, values, "outcome", "requirements")
