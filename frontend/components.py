# -*- coding: utf-8 -*-
"""
frontend/components.py -- Premium UI components for SupportFlow AI.

Design System
-------------
Colors:
  - Deep Navy/Slate: #0F172A, #1E293B
  - Primary Indigo: #5146C7, #4338A8
  - Soft Backgrounds: #FAF9F6, #F8FAFC, #EEF2FF
  - Badges: Green (#ECFDF3, #166534), Amber (#FFF7D6, #92400E), Red (#FEF2F2, #B91C1C), Purple (#F3E8FF, #6B21A8), Blue (#EEF2FF, #1E40AF)
"""

from __future__ import annotations

import re
import os
import base64
import streamlit as st

# ---------------------------------------------------------------------------
# Example buttons
# ---------------------------------------------------------------------------

EXAMPLES: list[str] = [
    "My product is damaged. I want a replacement for ORD004.",
    "Please cancel my order ORD007 and check whether I am eligible for a refund.",
    "Where is my package for order ORD009?",
]

_EXAMPLE_LABELS: list[str] = [
    "🔄 Replacement Request",
    "❌ Cancel & Refund",
    "🚚 Delivery Tracking",
]


def render_examples() -> str | None:
    """Render clickable quick demo scenario buttons."""
    st.caption("⚡ Quick Demo Scenarios:")
    cols = st.columns(len(EXAMPLES))
    for col, label, example in zip(cols, _EXAMPLE_LABELS, EXAMPLES):
        with col:
            if st.button(label, use_container_width=True, key=f"ex_{label}"):
                return example
    return None


# ---------------------------------------------------------------------------
# Status Badge Component
# ---------------------------------------------------------------------------

def render_status_badge(status_str: str | None) -> str:
    """Return an HTML snippet for a stylized status badge."""
    if not status_str:
        return "<span style='background:#F1F5F9; color:#475569; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>N/A</span>"
    
    s = str(status_str).upper().strip()
    
    if s in ['RESOLVED', 'COMPLETED', 'DELIVERED', 'SUCCESS', 'VERIFIED']:
        return f"<span style='background:#ECFDF3; color:#166534; border:1px solid #A7F3D0; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>✓ {status_str}</span>"
    elif s in ['PENDING', 'NEEDS_CLARIFICATION', 'RUNNING', 'IN_PROGRESS', 'DELAYED']:
        return f"<span style='background:#FFF7D6; color:#92400E; border:1px solid #FDE68A; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>⏳ {status_str}</span>"
    elif s in ['ESCALATED', 'OPEN', 'HIGH']:
        return f"<span style='background:#F3E8FF; color:#6B21A8; border:1px solid #DDD6FE; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>⚠️ {status_str}</span>"
    elif s in ['FAILED', 'REPLANNING', 'CANCELLED', 'REFUNDED', 'INELIGIBLE_TRANSACTION', 'CRITICAL']:
        return f"<span style='background:#FEF2F2; color:#B91C1C; border:1px solid #FCA5A5; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>✕ {status_str}</span>"
    elif s in ['SHIPPED', 'OUT_FOR_DELIVERY', 'CONFIRMED']:
        return f"<span style='background:#EEF2FF; color:#1E40AF; border:1px solid #BFDBFE; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>🚚 {status_str}</span>"
    else:
        return f"<span style='background:#F1F5F9; color:#475569; border:1px solid #CBD5E1; padding:0.25rem 0.75rem; border-radius:9999px; font-size:0.75rem; font-weight:700;'>{status_str}</span>"


# ---------------------------------------------------------------------------
# ID Validation Helpers
# ---------------------------------------------------------------------------

_ORDER_ID_RE = re.compile(r"^ORD\d+$", re.IGNORECASE)
_CUSTOMER_ID_RE = re.compile(r"^C\d+$", re.IGNORECASE)


def validate_order_id(raw: str) -> tuple[bool, str]:
    val = raw.strip().upper()
    if not val:
        return False, "Please enter your order ID, for example ORD005."
    if not _ORDER_ID_RE.match(val):
        return False, f"'{raw.strip()}' does not look like a valid order ID. Use format ORD005."
    return True, val


def validate_customer_id(raw: str) -> tuple[bool, str]:
    val = raw.strip().upper()
    if not val:
        return False, "Please enter your customer ID, for example C101."
    if not _CUSTOMER_ID_RE.match(val):
        return False, f"'{raw.strip()}' does not look like a valid customer ID. Use format C101."
    return True, val


def render_followup_input(missing: str) -> str | None:
    if missing == "order_id":
        label = "Order ID"
        placeholder = "e.g. ORD005"
        hint = "Please provide your order ID to proceed."
    else:
        label = "Customer ID"
        placeholder = "e.g. C101"
        hint = "Please provide your customer ID to proceed."

    st.warning(f"⚠️ Information Needed: {hint}")

    followup_value = st.text_input(
        label=label,
        placeholder=placeholder,
        key=f"followup_{missing}",
    )

    if st.button("➡️ Continue", type="primary", key="btn_continue"):
        return followup_value

    return None


# ---------------------------------------------------------------------------
# Find My Order Flow Widget
# ---------------------------------------------------------------------------

def render_find_my_order(orders_result: dict | None) -> str | None:
    if not st.session_state.get("fmo_show_email") and orders_result is None:
        st.warning("⚠️ Don't know your Order ID? We can look it up for you.")
        if st.button("🔍 Find My Order by Email", type="secondary", key="btn_find_my_order"):
            st.session_state.fmo_show_email = True
            st.session_state.fmo_orders_result = None
            st.rerun()
        return None

    if st.session_state.get("fmo_show_email") and st.session_state.get("fmo_orders_result") is None:
        st.markdown("#### 📧 Enter your registered email address")
        email_val = st.text_input("Email address", placeholder="e.g. aarav.sharma@example.com", key="fmo_email_input")

        col_find, col_back = st.columns([2, 1])
        with col_find:
            find_clicked = st.button("🔍 Search Orders", type="primary", key="btn_find_my_orders", use_container_width=True)
        with col_back:
            if st.button("Back", key="btn_fmo_back", use_container_width=True):
                st.session_state.fmo_show_email = False
                st.session_state.fmo_orders_result = None
                st.rerun()

        if find_clicked:
            raw_email = email_val.strip()
            if not raw_email or "@" not in raw_email:
                st.warning("Please enter a valid email address.")
            else:
                from frontend.api.data_api import fetch_orders
                result = fetch_orders(email=raw_email)
                st.session_state.fmo_orders_result = result
                st.rerun()
        return None

    result = st.session_state.get("fmo_orders_result")
    if result is None:
        return None

    if isinstance(result, dict) and not result.get("success", True):
        st.error(result.get("message", "We could not find an account with that email."))
        if st.button("Try a different email", key="btn_fmo_retry"):
            st.session_state.fmo_orders_result = None
            st.rerun()
        return None

    orders = result.get("orders", []) if isinstance(result, dict) else result
    customer_name = result.get("customer_name", "") if isinstance(result, dict) else "Customer"

    if not orders:
        st.info(f"Account found ({customer_name}), but no orders exist.")
        if st.button("Try a different email", key="btn_fmo_retry_empty"):
            st.session_state.fmo_orders_result = None
            st.session_state.fmo_show_email = False
            st.rerun()
        return None

    st.markdown(f"#### 🛒 Orders for **{customer_name}**")
    st.caption("Click on an order to select it for AI Support:")

    for i, order in enumerate(orders):
        order_id = order.get("order_id", "")
        product_name = order.get("product_name", "Product")
        status = order.get("status") or order.get("order_status", "UNKNOWN")
        amount = order.get("total_amount", 0)

        with st.container(border=True):
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.markdown(f"**🛍️ {product_name}** (`{order_id}`)")
                st.markdown(render_status_badge(status), unsafe_allow_html=True)
                st.caption(f"Total: ₹{float(amount):,.2f}")
            with col_btn:
                if st.button("Select Order", key=f"btn_sel_{i}_{order_id}", type="primary", use_container_width=True):
                    return order_id

    if st.button("Use a different email", key="btn_fmo_change"):
        st.session_state.fmo_orders_result = None
        st.session_state.fmo_show_email = False
        st.rerun()

    return None


# ---------------------------------------------------------------------------
# Product Images & Styling Helpers
# ---------------------------------------------------------------------------

_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "products")

_PRODUCT_IMAGES = {
    "Apple iPhone 15": "iphone15.jpg",
    "Samsung Galaxy S24": "samsung-s24.jpg",
    "ASUS Vivobook 15 Laptop": "asus-vivobook15.jpg",
    "boAt Airdopes 141 Earbuds": "boat-airdopes141.jpg",
    "Sony WH-1000XM5 Headphones": "sony-wh1000xm5.jpg",
    "Logitech MX Master 3 Mouse": "logitech-mx-master3.png",
    "Nike Air Max 270": "nike-air-max270.jpg",
    "Philips HD9200 Air Fryer": "philips-hd9200.jpg",
    "Python Crash Course (3rd Edition)": "python-crash-course.jpg",
    "Syska LED Smart Bulb 9W": "syska-led-bulb-9w.jpg"
}


def _get_image_data_uri(product_name: str) -> str:
    filename = _PRODUCT_IMAGES.get(product_name)
    if not filename:
        return ""
    filepath = os.path.join(_ASSETS_DIR, filename)
    if not os.path.exists(filepath):
        return ""
    try:
        with open(filepath, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        ext = filename.split('.')[-1].lower()
        if ext == 'jpg': ext = 'jpeg'
        return f"data:image/{ext};base64,{b64}"
    except Exception:
        return ""


def _get_product_emoji(product_name: str) -> str:
    lower = product_name.lower()
    if any(w in lower for w in ("iphone", "samsung", "galaxy", "phone")): return "📱"
    if any(w in lower for w in ("laptop", "notebook", "vivobook", "asus")): return "💻"
    if any(w in lower for w in ("headphone", "earphone", "earbuds", "sony", "boat")): return "🎧"
    if any(w in lower for w in ("shoe", "sneaker", "nike")): return "👟"
    if any(w in lower for w in ("mouse", "keyboard", "logitech")): return "🖱️"
    if any(w in lower for w in ("book", "course", "python")): return "📖"
    if any(w in lower for w in ("fryer", "oven", "philips")): return "🍳"
    if any(w in lower for w in ("bulb", "lamp", "syska")): return "💡"
    return "📦"


def render_product_card(product) -> bool:
    """Render a premium product card with image/fallback, details, and action button."""
    with st.container(border=True):
        image_url = _get_image_data_uri(getattr(product, "name", ""))
        emoji = _get_product_emoji(getattr(product, "name", ""))
        name = getattr(product, "name", "Product")
        category = getattr(product, "category", "Electronics")
        price = float(getattr(product, "price", 0))
        product_id = getattr(product, "product_id", "")
        stock = getattr(product, "stock", 10)

        if image_url:
            st.markdown(
                f'''
                <div style="background-color: #F8FAFC; border-radius: 10px; padding: 0.75rem; margin-bottom: 0.75rem; text-align: center; display: flex; align-items: center; justify-content: center; height: 160px;">
                    <img src="{image_url}" alt="{name}" style="max-height: 100%; max-width: 100%; object-fit: contain; border-radius: 6px;">
                </div>
                ''',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'''
                <div style="background-color: #EEF2FF; border-radius: 10px; padding: 0.75rem; margin-bottom: 0.75rem; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 160px;">
                    <div style="font-size: 3rem;">{emoji}</div>
                    <div style="color: #64748B; font-size: 0.8rem; margin-top: 0.25rem;">SupportFlow Catalog</div>
                </div>
                ''',
                unsafe_allow_html=True
            )

        st.markdown(f"<h4 style='margin-bottom: 2px; font-weight: 700;'>{name}</h4>", unsafe_allow_html=True)
        st.markdown(f"<p style='color: #64748B; font-size: 0.85rem; margin-top: 0;'>{category} • <code>{product_id}</code></p>", unsafe_allow_html=True)
        
        stock_badge = "<span style='color: #166534; font-size: 0.8rem; font-weight: 600;'>In Stock</span>" if stock > 0 else "<span style='color: #B91C1C; font-size: 0.8rem;'>Out of Stock</span>"
        
        col_price, col_stock = st.columns([2, 1])
        with col_price:
            st.markdown(f"<h3 style='color: #0F172A; margin: 0; font-weight: 800;'>₹{price:,.2f}</h3>", unsafe_allow_html=True)
        with col_stock:
            st.markdown(f"<div style='text-align: right; margin-top: 6px;'>{stock_badge}</div>", unsafe_allow_html=True)

        st.markdown("<div style='margin-bottom: 0.75rem;'></div>", unsafe_allow_html=True)

        return st.button("View Details", key=f"view_product_{product_id}", use_container_width=True, type="primary")


# ---------------------------------------------------------------------------
# Context Card Widget
# ---------------------------------------------------------------------------

def render_support_context(context: dict) -> None:
    """Render a clean Support Context banner when launched from Shop or Orders."""
    order_id = context.get("order_id")
    product_id = context.get("product_id")
    customer_id = context.get("customer_id")

    if not order_id and not product_id:
        return

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="background-color: #F0E9FF; border-radius: 8px; padding: 0.75rem 1rem; border: 1px solid #DCC7F5; margin-bottom: 1rem;">
                <div style="font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 800; color: #6B21A8; margin-bottom: 4px;">🎯 Active Support Context</div>
                <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: center; font-size: 0.95rem; color: #1E293B;">
                    {f"<span><strong>Order:</strong> <code>{order_id}</code></span>" if order_id else ""}
                    {f"<span><strong>Product:</strong> <code>{product_id}</code></span>" if product_id else ""}
                    {f"<span><strong>Customer:</strong> <code>{customer_id}</code></span>" if customer_id else ""}
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ---------------------------------------------------------------------------
# Resolution & Activity Panel Components
# ---------------------------------------------------------------------------

def render_resolution(final_response: str, resolved: bool, hide_clarification: bool = False) -> None:
    """Display resolution text with status badges."""
    if hide_clarification:
        return

    st.markdown("### 🎯 Support Resolution")

    with st.container(border=True):
        badge_html = render_status_badge("RESOLVED" if resolved else "NEEDS_CLARIFICATION")
        st.markdown(f"<div style='margin-bottom: 0.75rem;'>{badge_html}</div>", unsafe_allow_html=True)
        st.markdown(final_response)

        ticket_match = re.search(r'(TKT-\d+)', final_response)
        if ticket_match:
            ticket_id = ticket_match.group(1)
            st.markdown(
                f"""
                <div style="background: #F5EEFF; border: 1px solid #DCC7F5; padding: 1rem; border-radius: 8px; margin-top: 1rem;">
                    <h4 style="margin: 0 0 8px 0; color: #6B21A8;">🎫 Support Ticket Created</h4>
                    <p style="margin: 0; font-size: 0.95rem;"><strong>Ticket ID:</strong> <code>{ticket_id}</code></p>
                    <p style="margin: 4px 0 0 0; color: #6B21A8; font-size: 0.85rem;">Our customer care team has received your context and will follow up shortly.</p>
                </div>
                """,
                unsafe_allow_html=True
            )


def render_workflow_activity_panel(workflow_trace: list[dict] | None = None, workflow_plan: dict | None = None) -> None:
    """Render Task 11 vertical workflow execution timeline."""
    wf_trace = workflow_trace or []
    wf_plan = workflow_plan or {}

    if not wf_trace and not wf_plan:
        return

    st.markdown("### ⚡ Workflow Execution Trace")

    with st.container(border=True):
        if wf_plan and wf_plan.get("goal"):
            st.markdown(f"**Goal:** `{wf_plan.get('goal')}`")

        trace_items = wf_trace if wf_trace else [
            {"step": s.get("action"), "status": s.get("status")}
            for s in wf_plan.get("steps", [])
        ]

        if trace_items:
            status_styles = {
                "COMPLETED": ("✓", "#166534", "#ECFDF3", "#A7F3D0"),
                "FAILED": ("✕", "#991B1B", "#FEF2F2", "#FCA5A5"),
                "SKIPPED": ("⏭", "#475569", "#F1F5F9", "#CBD5E1"),
                "RUNNING": ("⚡", "#1E40AF", "#EEF2FF", "#BFDBFE"),
                "PENDING": ("⏳", "#854D0E", "#FFF7D6", "#FDE68A"),
            }

            for idx, item in enumerate(trace_items):
                step_name = item.get("step", f"step_{idx+1}").replace("_", " ").title()
                step_status = str(item.get("status", "PENDING")).upper()
                icon, text_color, bg_color, border_color = status_styles.get(step_status, ("•", "#1E293B", "#F8FAFC", "#E2E8F0"))

                st.markdown(
                    f"""
                    <div style="background-color: {bg_color}; border: 1px solid {border_color}; border-radius: 8px; padding: 0.6rem 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <span style="font-weight: 700; color: {text_color}; font-size: 0.95rem;">Step {idx+1}: {step_name}</span>
                        </div>
                        <div>
                            <span style="font-weight: 700; font-size: 0.8rem; color: {text_color}; border: 1px solid {border_color}; padding: 2px 8px; border-radius: 12px; background: #FFFFFF;">{icon} {step_status}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )


def render_agent_activity_panel(result: dict) -> None:
    """Render Agent Activity & Policy Decision Metrics."""
    decision = result.get("decision") or {}
    verification = result.get("verification") or {}
    policy_ctx = result.get("policy_context") or {}

    if not decision and not verification and not policy_ctx:
        return

    with st.expander("🔍 Agentic Inspection & Decision Details", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Intent:** `{result.get('intent', 'N/A')}`")
            st.markdown(f"**Agent:** `{decision.get('selected_agent', result.get('selected_agent', 'N/A'))}`")
        with c2:
            st.markdown(f"**Order ID:** `{result.get('order_id', 'N/A')}`")
            st.markdown(f"**Action:** `{decision.get('selected_action', result.get('selected_action', 'N/A'))}`")
        with c3:
            st.markdown(f"**Final Status:** `{result.get('final_status', 'N/A')}`")
            v_status = verification.get("verified") if isinstance(verification, dict) else None
            st.markdown(f"**Verification:** `{'Verified ✓' if v_status else 'Unverified'}`")

        if decision.get("rationale"):
            st.info(f"**Decision Rationale:** {decision.get('rationale')}")


# ---------------------------------------------------------------------------
# Empty & Error States
# ---------------------------------------------------------------------------

def render_empty_state(title: str, message: str, icon: str = "📦") -> None:
    """Render a stylized empty state component."""
    st.markdown(
        f"""
        <div style="background-color: #FFFFFF; border: 1px dashed #CBD5E1; border-radius: 12px; padding: 3rem 2rem; text-align: center; margin: 1.5rem 0;">
            <div style="font-size: 3rem; margin-bottom: 0.5rem;">{icon}</div>
            <h3 style="color: #0F172A; font-weight: 700; margin-bottom: 0.5rem;">{title}</h3>
            <p style="color: #64748B; max-width: 450px; margin: 0 auto; font-size: 0.95rem;">{message}</p>
        </div>
        """,
        unsafe_allow_html=True
    )


def render_error_state(title: str, message: str) -> None:
    """Render a human-friendly API error component."""
    st.markdown(
        f"""
        <div style="background-color: #FEF2F2; border: 1px solid #FCA5A5; border-radius: 12px; padding: 1.5rem; margin: 1rem 0;">
            <h4 style="color: #991B1B; margin: 0 0 0.5rem 0; font-weight: 700;">⚠️ {title}</h4>
            <p style="color: #7F1D1D; margin: 0; font-size: 0.95rem;">{message}</p>
        </div>
        """,
        unsafe_allow_html=True
    )