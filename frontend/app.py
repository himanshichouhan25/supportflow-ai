"""
frontend/app.py -- SupportFlow AI Streamlit Demo

Run from the project root:
    .venv\\Scripts\\streamlit.exe run frontend/app.py

The app calls the CoordinatorAgent directly -- no extra HTTP server needed.
No LLM calls happen on page load; only when the user clicks "Resolve Issue".
"""

from __future__ import annotations

import sys
import os

# ---------------------------------------------------------------------------
# Path setup -- allow imports from the project root (backend/, agents/, tools/)
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st

from agents.coordinator import run_coordinator
from frontend.components import (
    EXAMPLES,
    render_examples,
    render_resolution,
    render_sidebar,
    render_workflow,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SupportFlow AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Minimal global style tweaks -- keeps font clean without heavy CSS
st.markdown(
    """
    <style>
    /* Tighten top padding */
    .block-container { padding-top: 2rem; }

    /* Subtle card shadow for st.container */
    div[data-testid="stVerticalBlock"] > div:has(> .stMarkdown) {
        border-radius: 8px;
    }

    /* Make metric labels slightly smaller */
    [data-testid="metric-container"] label {
        font-size: 0.78rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
render_sidebar()

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    """
    <h1 style="margin-bottom:0; font-size:2.2rem;">🧠 SupportFlow AI</h1>
    <p style="color:#6b7280; font-size:1.05rem; margin-top:4px;">
        Multi-Agent Customer Support Resolution System
    </p>
    <hr style="margin: 12px 0 20px 0; border-color:#e5e7eb;"/>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
if "result" not in st.session_state:
    st.session_state.result = None
if "user_message" not in st.session_state:
    st.session_state.user_message = ""

# ---------------------------------------------------------------------------
# Section 1: Customer Issue
# ---------------------------------------------------------------------------
st.markdown("## 1️⃣  Customer Issue")

# Example buttons -- clicking one pre-fills the text area
selected_example = render_examples()
if selected_example:
    st.session_state.user_message = selected_example

user_message: str = st.text_area(
    label="Describe your issue",
    value=st.session_state.user_message,
    height=100,
    placeholder="My payment was successful but my iPhone 15 order is still pending.",
    key="input_area",
)

col_btn, col_clear = st.columns([1, 6])
with col_btn:
    resolve_clicked = st.button(
        "🔍 Resolve Issue",
        type="primary",
        use_container_width=True,
    )
with col_clear:
    if st.button("Clear", use_container_width=False):
        st.session_state.result = None
        st.session_state.user_message = ""
        st.rerun()

# ---------------------------------------------------------------------------
# Run coordinator ONLY when button is clicked
# ---------------------------------------------------------------------------
if resolve_clicked:
    msg = user_message.strip()
    if not msg:
        st.warning("Please describe your issue before clicking Resolve.")
    else:
        with st.spinner("SupportFlow AI is working on your request..."):
            try:
                result = run_coordinator(msg)
                st.session_state.result = result
            except Exception as exc:
                st.error(f"An error occurred: {exc}")
                st.session_state.result = None

# ---------------------------------------------------------------------------
# Sections 2 & 3: Workflow + Resolution (shown after coordinator runs)
# ---------------------------------------------------------------------------
if st.session_state.result:
    result = st.session_state.result
    steps  = result.get("steps", [])

    st.markdown("---")

    # Two-column layout: workflow left, resolution right
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown("## 2️⃣  Agent Workflow")
        render_workflow(steps)

    with right_col:
        st.markdown("## 3️⃣  Final Resolution")
        render_resolution(result)

# ---------------------------------------------------------------------------
# Empty state hint
# ---------------------------------------------------------------------------
else:
    st.markdown("---")
    st.markdown(
        """
        <div style="
            text-align:center;
            padding: 48px 24px;
            color: #9ca3af;
        ">
            <div style="font-size:3rem;">🤖</div>
            <div style="font-size:1.05rem; margin-top:12px;">
                Enter a support issue above and click <strong>Resolve Issue</strong>
                to see the agentic workflow in action.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
