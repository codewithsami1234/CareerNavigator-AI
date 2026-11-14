"""Welcome band. It does not display analysis figures."""
from __future__ import annotations

import streamlit as st


def render_hero() -> None:
    st.markdown(
        """
        <section class="cn-hero">
          <div>
            <p class="cn-kicker">CareerNavigator AI</p>
            <h2>Navigate Your Career With Intelligence.</h2>
            <p>Turn your skills, experience, and career goals into actionable insights.</p>
          </div>
          <div class="cn-orb" aria-hidden="true"></div>
        </section>
        """,
        unsafe_allow_html=True,
    )
