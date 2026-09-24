"""
frontend/components.py -- Reusable Streamlit UI components for SupportFlow AI.

Keeps app.py clean by centralising rendering logic.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------

AGENT_META: dict[str, dict[str, str]] = {
    "Coordinator":    {"icon": "🤖", "color": "#6366f1"},
    "OrderAgent":     {"icon": "📦", "color": "#f59e0b"},
    "PaymentAgent":   {"icon": "💳", "color": "#10b981"},
    "DeliveryAgent":  {"icon": "🚚", "color": "#3b82f6"},
    "AccountAgent":   {"icon": "👤", "color": "#8b5cf6"},
}

STATUS_ICON: dict[str, str] = {
    "completed":  "✅",
    "replanning": "🔄",
    "error":      "❌",
}


def _agent_icon(agent_name: str) -> str:
    for key, meta in AGENT_META.items():
        if key.lower() in agent_name.lower():
            return meta["icon"]
    return "🤖"


def _status_icon(status: str) -> str:
    return STATUS_ICON.get(status, "⏳")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    """Render the left sidebar with system info and agent list."""
    with st.sidebar:
        st.markdown("## 🧠 SupportFlow AI")
        st.markdown("---")
        st.markdown(
            "**Agentic Workflow**\n\n"
            "`Understand` → `Route` → `Tool` → `Observe` → `Replan` → `Resolve`"
        )
        st.markdown("---")
        st.markdown("### Specialist Agents")
        agents = [
            ("📦", "Order Agent",    "check_order, cancel_order"),
            ("💳", "Payment Agent",  "check_payment, refund_eligibility"),
            ("🚚", "Delivery Agent", "check_delivery"),
            ("👤", "Account Agent",  "check_account"),
        ]
        for icon, name, tools in agents:
            st.markdown(f"{icon} **{name}**")
            st.caption(f"Tools: {tools}")

        st.markdown("---")
        st.caption(
            "Powered by **FastAPI** · **PostgreSQL** · **Python** · **Gemini AI**\n\n"
            "_Demo data only. Not affiliated with any real retailer._"
        )


# ---------------------------------------------------------------------------
# Example queries
# ---------------------------------------------------------------------------

EXAMPLES: list[str] = [
    "My payment was successful but my iPhone 15 order ORD005 is still pending.",
    "Cancel my order ORD007 and check whether I can get a refund.",
    "Where is my package for ORD009?",
]


def render_examples() -> str | None:
    """
    Render clickable example query buttons.

    Returns the selected example text, or None if nothing was clicked.
    """
    st.markdown("##### Try a demo scenario:")
    cols = st.columns(len(EXAMPLES))
    labels = [
        "💳 Payment + Order",
        "❌ Cancel + Refund",
        "🚚 Delivery Tracking",
    ]
    for col, label, example in zip(cols, labels, EXAMPLES):
        with col:
            if st.button(label, use_container_width=True, key=f"ex_{label}"):
                return example
    return None


# ---------------------------------------------------------------------------
# Workflow visualisation
# ---------------------------------------------------------------------------

def render_workflow(steps: list[dict[str, Any]]) -> None:
    """Render the agent workflow trace as a vertical step timeline."""
    if not steps:
        st.info("No workflow steps to display.")
        return

    st.markdown("### 🔀 Agent Workflow")

    for i, step in enumerate(steps):
        agent  = step.get("agent", "Unknown")
        action = step.get("action", "")
        tool   = step.get("tool", "")
        status = step.get("status", "completed")
        icon   = _agent_icon(agent)
        s_icon = _status_icon(status)

        # Pick background tint based on agent/status
        if status == "replanning":
            bg = "#fef3c7"
            border = "#f59e0b"
        elif "Coordinator" in agent:
            bg = "#f0f4ff"
            border = "#6366f1"
        else:
            bg = "#f0fdf4"
            border = "#10b981"

        step_html = f"""
        <div style="
            background:{bg};
            border-left: 4px solid {border};
            border-radius: 6px;
            padding: 10px 16px;
            margin-bottom: 4px;
        ">
            <span style="font-weight:700; font-size:0.85rem; color:#374151;">
                Step {step.get('step', i+1)} &nbsp;·&nbsp; {icon} {agent}
            </span><br/>
            <span style="font-size:0.9rem; color:#1f2937;">{action}</span>
            {"<br/><span style='font-size:0.8rem;color:#6b7280;'>Tool: <code>" + tool + "</code></span>" if tool else ""}
            <br/><span style="font-size:0.78rem; color:#6b7280;">{s_icon} {status.capitalize()}</span>
        </div>
        """
        st.markdown(step_html, unsafe_allow_html=True)

        # Arrow between steps (not after last)
        if i < len(steps) - 1:
            st.markdown(
                "<div style='text-align:center;color:#9ca3af;font-size:1.2rem;margin:-2px 0;'>↓</div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Final resolution panel
# ---------------------------------------------------------------------------

def render_resolution(result: dict[str, Any]) -> None:
    """Render the final resolution card."""
    st.markdown("### 🎯 Final Resolution")

    response = result.get("final_response", "No response generated.")
    resolved = result.get("resolved", False)
    intent   = result.get("intent", "unknown")
    intents  = result.get("intents", [])
    steps    = result.get("steps", [])

    specialist_calls = sum(
        1 for s in steps
        if s.get("agent", "Coordinator") != "Coordinator"
    )

    # Resolution badge
    badge_color = "#10b981" if resolved else "#f59e0b"
    badge_text  = "Resolved" if resolved else "Partially Resolved"

    st.markdown(
        f"""
        <div style="
            background:#ffffff;
            border:1px solid #e5e7eb;
            border-radius:10px;
            padding:20px;
            box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        ">
            <div style="margin-bottom:12px;">
                <span style="
                    background:{badge_color};
                    color:white;
                    padding:3px 12px;
                    border-radius:99px;
                    font-size:0.78rem;
                    font-weight:600;
                ">{badge_text}</span>
            </div>
            <p style="font-size:1.05rem; color:#111827; line-height:1.6; margin:0;">
                {response}
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")  # spacer

    # Metadata row
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Primary Intent", intent.capitalize())
    with c2:
        st.metric("Intents Detected", len(intents))
    with c3:
        st.metric("Specialist Calls", specialist_calls)

    # Show replanning badge if multi-agent
    if specialist_calls > 1:
        st.success(
            f"🔄 Multi-agent workflow: {specialist_calls} specialists "
            f"collaborated to resolve your request."
        )
