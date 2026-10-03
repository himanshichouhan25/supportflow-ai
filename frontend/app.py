# -*- coding: utf-8 -*-
"""
frontend/app.py — SupportFlow AI customer-facing Streamlit app.

Run from the project root:
    .venv\Scripts\streamlit.exe run frontend/app.py

The internal multi-agent coordinator runs in the background.
No agent names, tool names, workflow steps, or internal data are
shown to the customer.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import streamlit as st
from sqlalchemy import select

from agents.coordinator import run_coordinator
from backend.database import SessionLocal
from backend.models.product import Product

from frontend.components import (
    render_examples,
    render_find_my_order,
    render_followup_input,
    render_product_card,
    render_resolution,
    validate_customer_id,
    validate_order_id,
)

from tools.order_tool import find_orders_by_email
from tools.payment_tool import check_payment
from tools.delivery_tool import check_delivery


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SupportFlow AI",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)


if "custom_sidebar_open" not in st.session_state:
    st.session_state.custom_sidebar_open = True

# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Premium SaaS overrides */
    :root {
        --primary-color: #5146C7;
        --border-color: #E2E0DC;
        --sidebar-border: #D9D7EA;
    }
    
    /* Global Backgrounds */
    [data-testid="stAppViewContainer"] {
        background-color: #FAF9F6 !important;
    }
    [data-testid="stSidebar"] {
        background-color: #E9E7F8 !important;
        border-right: 1px solid var(--sidebar-border) !important;
    }
    
    .block-container {
        padding-top: 1rem;
        padding-bottom: 4rem;
        max-width: 1000px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Header visibility overrides */
    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
    }
    
    [data-testid="stToolbar"], .stAppDeployButton {
        visibility: hidden !important;
    }
    
    /* Hide all native sidebar toggle elements */
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* Custom Expand Button Styling */
    div:has(> #expand-button-hook) + div.stButton {
        position: fixed !important;
        top: 1rem !important;
        left: 1rem !important;
        z-index: 999999 !important;
    }
    div:has(> #expand-button-hook) + div.stButton button {
        background: #FFFFFF !important;
        border: 1px solid #D6D3E8 !important;
        color: #4338A8 !important;
        border-radius: 8px !important;
        width: 36px !important;
        height: 36px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    div:has(> #expand-button-hook) + div.stButton button:hover {
        background: #F1F0FA !important;
    }
    div:has(> #expand-button-hook) + div.stButton button p {
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        margin: 0 !important;
        color: #4338A8 !important;
    }

    /* Custom Collapse Button Styling */
    div:has(> #collapse-button-hook) + div.stButton button {
        background: transparent !important;
        border: none !important;
        color: #5F6680 !important;
        width: auto !important;
        padding: 0 !important;
        float: right;
        box-shadow: none !important;
    }
    div:has(> #collapse-button-hook) + div.stButton button:hover {
        background: transparent !important;
        transform: scale(1.1);
    }
    div:has(> #collapse-button-hook) + div.stButton button p {
        font-size: 1.2rem !important;
        font-weight: 800 !important;
        color: #5F6680 !important;
    }

    
    /* Ensure all text has good contrast */
    h1, h2, h3, h4, h5, h6 {
        color: #172033 !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }
    p, span, div {
        color: #172033;
    }
    
    /* Cards and Containers */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03) !important;
        padding: 1.5rem !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    
    /* SECTION HOOKS */
    div[style*="border"]:has(#shop-header-hook) {
        background-color: #FFF4E6 !important;
        border-color: #FFE5CC !important;
    }
    div[style*="border"]:has(#shop-search-hook) {
        background-color: #EEF6FF !important;
        border-color: #DDEBFF !important;
    }
    div[style*="border"]:has(#my-orders-hook) {
        background-color: #EAF4FF !important;
        border-color: #DDEBFF !important;
    }
    div[style*="border"]:has(#ai-support-hook) {
        background-color: #F0E9FF !important;
        border-color: #DCC7F5 !important;
    }
    div[style*="border"]:has(#ai-input-hook) {
        background-color: #F3F1FF !important;
        border-color: #D8D4F0 !important;
    }
    div[style*="border"]:has(#resolution-hook) {
        background-color: #EEF9F4 !important;
        border-color: #CCF0E1 !important;
    }
    
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] {
        background: #E8F1FF !important;
        padding: 1rem !important;
        border-radius: 12px !important;
        margin-bottom: 1.5rem !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        background: #DDE7FF !important;
    }
    
    /* Primary Buttons */
    button[kind="primary"] {
        background: #5146C7 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        box-shadow: 0 4px 6px -1px rgba(81, 70, 199, 0.4) !important;
    }
    button[kind="primary"]:hover {
        background: #4338A8 !important;
        box-shadow: 0 6px 8px -1px rgba(81, 70, 199, 0.5) !important;
        transform: translateY(-1px);
        color: #FFFFFF !important;
    }
    button[kind="primary"] p {
        color: #FFFFFF !important;
    }
    
    /* Secondary Buttons */
    button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #374151 !important;
        border: 1px solid #D6D3E8 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="secondary"]:hover {
        background: #F1F0FA !important;
        border-color: #D6D3E8 !important;
        color: #374151 !important;
    }
    button[kind="secondary"] p {
        color: #374151 !important;
    }
    
    /* AI Quick Action Buttons */
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] button {
        border-radius: 8px !important;
        font-weight: 600 !important;
        transition: all 0.2s ease;
        color: #172033 !important;
        border: none !important;
    }
    
    /* Specific Quick Actions Colors */
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] > div:nth-child(1) button {
        background: #E8F1FF !important;
    }
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] > div:nth-child(2) button {
        background: #FCEFF5 !important;
    }
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] > div:nth-child(3) button {
        background: #FFF1E6 !important;
    }

    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] button:hover {
        filter: brightness(0.95);
        color: #172033 !important;
    }
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] button:active {
        background: #5146C7 !important;
        color: #FFFFFF !important;
    }
    div:has(> #ai-quick-actions-hook) ~ div[data-testid="stHorizontalBlock"] button p {
        color: inherit !important;
    }
    
    /* Text Input Area */
    .stTextArea textarea {
        background: #FFFFFF !important;
        border: 1px solid #D6D3E8 !important;
        border-radius: 12px !important;
        font-size: 1.05rem !important;
        padding: 1rem !important;
        color: #172033 !important;
        box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.02) !important;
    }
    .stTextArea textarea:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 2px rgba(81, 70, 199, 0.2) !important;
    }
    .stTextArea textarea::placeholder {
        color: #7B8498 !important;
        opacity: 1 !important;
    }
    
    .stTextInput input {
        background: #FFFFFF !important;
        border: 1px solid #D6D3E8 !important;
        border-radius: 8px !important;
        color: #172033 !important;
    }
    .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 2px rgba(81, 70, 199, 0.2) !important;
    }
    .stTextInput input::placeholder {
        color: #7B8498 !important;
        opacity: 1 !important;
    }
    
    /* Enforce alert contrast */
    [data-testid="stAlert"] {
        color: #172033 !important;
    }
    [data-testid="stAlert"] * {
        color: #172033 !important;
    }

    /* Sidebar Navigation overrides */
    [data-testid="stSidebar"] {
        border-right: 1px solid var(--sidebar-border) !important;
    }
    
    [data-testid="stSidebar"] button[kind="primary"] {
        background: #4338A8 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 4px rgba(67, 56, 168, 0.2) !important;
    }
    [data-testid="stSidebar"] button[kind="primary"] p {
        color: #FFFFFF !important;
    }
    [data-testid="stSidebar"] button[kind="primary"]:hover {
        background: #4338A8 !important;
        color: #FFFFFF !important;
        transform: none !important;
    }
    
    [data-testid="stSidebar"] button[kind="secondary"] {
        background: transparent !important;
        color: #374151 !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"] p {
        color: #374151 !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: #DCD9F5 !important;
        color: #374151 !important;
    }
    [data-testid="stSidebar"] button[kind="secondary"]:hover p {
        color: #374151 !important;
    }
    [data-testid="stSidebar"] button p {
        text-align: left !important;
        flex-grow: 1;
        margin-left: 0.5rem;
    }

    /* Main Window Navigation Bar */
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] {
        background: #FFFFFF !important;
        border: 1px solid #E5E2DC !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
        margin-bottom: 2rem !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.02) !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button {
        width: 100% !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="secondary"] {
        background: transparent !important;
        border: none !important;
        color: #475569 !important;
        box-shadow: none !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="secondary"] p {
        color: #475569 !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover {
        background: #EEF2FF !important;
        color: #5146C7 !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="secondary"]:hover p {
        color: #5146C7 !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button[kind="primary"] {
        background: #5146C7 !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: none !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)





# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

_STATE_DEFAULTS = [
    ("page", "shop"),
    ("result", None),
    ("original_request", ""),
    ("pending_input", ""),
    ("fmo_show_email", False),
    ("fmo_orders_result", None),
    ("fmo_selected_id", None),
    ("selected_product_id", None),
    ("my_orders_result", None),
    ("my_orders_email", ""),
]

for _key, _default in _STATE_DEFAULTS:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_fmo_state() -> None:
    """Reset Find My Order state."""
    st.session_state.fmo_show_email = False
    st.session_state.fmo_orders_result = None
    st.session_state.fmo_selected_id = None


def _reset_my_orders_state() -> None:
    """Reset My Orders state."""
    st.session_state.my_orders_result = None
    st.session_state.my_orders_email = ""


def _reset_support_state() -> None:
    """
    Clear all previous support conversation state.

    Important:
    When moving from Product Details -> Support, the old resolution
    must not remain visible.
    """
    st.session_state.result = None
    st.session_state.original_request = ""
    st.session_state.pending_input = ""
    _reset_fmo_state()


def _needs_followup(result: dict | None) -> str | None:
    """
    Return the missing-ID type when the coordinator requires
    additional information.
    """
    if result is None:
        return None

    if result.get("resolved"):
        return None

    return result.get("missing")


def _fetch_products() -> list[Product]:
    """Fetch all products dynamically from PostgreSQL."""
    db = SessionLocal()

    try:
        products = db.scalars(
            select(Product).order_by(Product.name.asc())
        ).all()

        return list(products)

    finally:
        db.close()


def _fetch_product(product_id: str) -> Product | None:
    """Fetch one product by business product ID."""
    db = SessionLocal()

    try:
        return db.scalar(
            select(Product).where(Product.product_id == product_id)
        )

    finally:
        db.close()


def _fetch_order_extra_details(order_id: str) -> dict:
    """
    Fetch payment and delivery information for one order.

    Business logic remains inside the existing deterministic tools.
    """
    db = SessionLocal()

    try:
        payment_result = check_payment(order_id, db)
        delivery_result = check_delivery(order_id, db)

        return {
            "payment": payment_result,
            "delivery": delivery_result,
        }

    finally:
        db.close()


def _load_my_orders(email: str) -> dict:
    """Fetch customer orders using the existing order lookup tool."""
    db = SessionLocal()

    try:
        return find_orders_by_email(email, db)

    finally:
        db.close()


def _render_order_card(order: dict) -> None:
    """Render one customer order with payment and delivery details."""

    order_id = order.get("order_id", "")
    product_name = order.get("product_name", "Product")
    amount = order.get("total_amount", 0)
    order_status = order.get("status", "UNKNOWN")
    order_date = order.get("order_date", "")

    extra = _fetch_order_extra_details(order_id)

    payment = extra.get("payment", {})
    delivery = extra.get("delivery", {})

    payment_status = payment.get("status", "Not available")

    delivery_status = delivery.get("status", "Not available")
    tracking_id = delivery.get("tracking_id")
    expected_date = delivery.get("expected_date")

    with st.container(border=True):

        top_left, top_right = st.columns([3, 1])

        with top_left:
            st.markdown(f"#### 🛍️ {product_name}")
            st.markdown(f"<p style='color: #64748b; font-size: 0.85rem; margin-top: -10px;'>Order ID: <strong>{order_id}</strong></p>", unsafe_allow_html=True)

        with top_right:
            st.markdown(
                f"<h3 style='color: #0f172a; text-align: right; margin-top: 0;'>₹{float(amount):,.2f}</h3>",
                unsafe_allow_html=True
            )

        st.markdown("<hr style='border-top: 1px solid #E2E0DC; margin: 0.5rem 0 1rem 0;'>", unsafe_allow_html=True)

        def get_badge(status):
            s = status.upper()
            if s in ['SUCCESS', 'DELIVERED']: return f"<span style='background:#ECFDF3; color:#166534; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['PENDING', 'DELAYED']: return f"<span style='background:#FFF7D6; color:#92400E; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['FAILED']: return f"<span style='background:#FEF2F2; color:#B91C1C; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['REFUNDED', 'CANCELLED']: return f"<span style='background:#FEF2F2; color:#B91C1C; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['SHIPPED', 'OUT_FOR_DELIVERY', 'CONFIRMED']: return f"<span style='background:#EEF2FF; color:#4338A8; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['OPEN']: return f"<span style='background:#F3E8FF; color:#6B21A8; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            return f"<span style='background:#F1F5F9; color:#475569; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"

        info_1, info_2, info_3 = st.columns(3)

        with info_1:
            st.markdown("<p style='color: #64748b; font-size: 0.85rem; margin-bottom: 4px;'>Order Status</p>", unsafe_allow_html=True)
            st.markdown(get_badge(order_status), unsafe_allow_html=True)

        with info_2:
            st.markdown("<p style='color: #64748b; font-size: 0.85rem; margin-bottom: 4px;'>Payment</p>", unsafe_allow_html=True)
            if payment_status != "Not available":
                st.markdown(get_badge(payment_status), unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #94a3b8; font-size: 0.85rem;'>Not available</span>", unsafe_allow_html=True)

        with info_3:
            st.markdown("<p style='color: #64748b; font-size: 0.85rem; margin-bottom: 4px;'>Delivery</p>", unsafe_allow_html=True)
            if delivery_status != "Not available":
                st.markdown(get_badge(delivery_status), unsafe_allow_html=True)
            else:
                st.markdown("<span style='color: #94a3b8; font-size: 0.85rem;'>Not available</span>", unsafe_allow_html=True)

        if order_date:
            st.caption(f"📅 Ordered on {order_date}")

        delivery_details = []

        if tracking_id:
            delivery_details.append(
                f"**Tracking ID:** {tracking_id}"
            )

        if expected_date:
            delivery_details.append(
                f"**Expected:** {expected_date}"
            )

        if delivery_details:
            st.markdown(" • ".join(delivery_details))

        st.markdown("")

        if st.button(
            "💬 Get Support",
            key=f"order_support_{order_id}",
            use_container_width=True,
        ):
            _reset_support_state()

            st.session_state.original_request = (
                f"I need help with my order. "
                f"Order ID: {order_id}"
            )

            st.session_state.pending_input = (
                f"I need help with Order ID: {order_id}."
            )

            st.session_state.page = "support"

            st.rerun()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="background-color: #EEF2FF; padding: 2rem; border-radius: 16px; text-align: center; margin-bottom: 1.5rem;">
        <h2 style="color: #172033; font-weight: 800; margin-bottom: 0;">🧠 SupportFlow AI</h2>
        <p style="color: #64748b; font-size: 1.05rem; margin-top: 0.25rem;">Smart shopping support powered by AI</p>
    </div>
    """, 
    unsafe_allow_html=True
)

# ---------------------------------------------------------------------------
# Main Window Navigation
# ---------------------------------------------------------------------------

st.markdown('<div id="main-nav-hook"></div>', unsafe_allow_html=True)
nav_container = st.container()
with nav_container:
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🛍 Shop", use_container_width=True, type="primary" if st.session_state.page == "shop" else "secondary", key="main_nav_shop"):
            st.session_state.page = "shop"
            st.session_state.selected_product_id = None
            _reset_support_state()
            _reset_my_orders_state()
            st.rerun()

    with col2:
        if st.button("📦 My Orders", use_container_width=True, type="primary" if st.session_state.page == "orders" else "secondary", key="main_nav_orders"):
            st.session_state.page = "orders"
            st.session_state.selected_product_id = None
            _reset_support_state()
            st.rerun()

    with col3:
        if st.button("💬 AI Support", use_container_width=True, type="primary" if st.session_state.page == "support" else "secondary", key="main_nav_support"):
            st.session_state.page = "support"
            st.session_state.selected_product_id = None
            _reset_support_state()
            _reset_my_orders_state()
            st.rerun()


# ---------------------------------------------------------------------------
# Navigation (Sidebar Only)
# ---------------------------------------------------------------------------

if not st.session_state.custom_sidebar_open:
    st.markdown("""
        <style>
        [data-testid="stSidebar"] {
            display: none !important;
        }
        </style>
    """, unsafe_allow_html=True)
    st.markdown('<div id="expand-button-hook"></div>', unsafe_allow_html=True)
    if st.button("»", key="btn_expand_sidebar"):
        st.session_state.custom_sidebar_open = True
        st.rerun()

with st.sidebar:
    st.markdown('<div id="collapse-button-hook"></div>', unsafe_allow_html=True)
    if st.button("«", key="btn_collapse_sidebar"):
        st.session_state.custom_sidebar_open = False
        st.rerun()

    st.markdown(
        """
        <div style="margin-top: -1.5rem; margin-bottom: 2rem;">
            <h3 style="color: #172033; font-weight: 800; margin-bottom: 0;">🧠 SupportFlow AI</h3>
            <p style="color: #5F6680; font-size: 0.9rem; margin-top: 0.2rem;">AI Customer Support<br>Resolution Assistant</p>
        </div>
        """, unsafe_allow_html=True
    )
    
    if st.button("🛍 Shop", use_container_width=True, type="primary" if st.session_state.page == "shop" else "secondary", key="sb_shop"):
        st.session_state.page = "shop"
        st.session_state.selected_product_id = None
        _reset_support_state()
        _reset_my_orders_state()
        st.rerun()

    if st.button("📦 My Orders", use_container_width=True, type="primary" if st.session_state.page == "orders" else "secondary", key="sb_orders"):
        st.session_state.page = "orders"
        st.session_state.selected_product_id = None
        _reset_support_state()
        st.rerun()

    if st.button("💬 AI Support", use_container_width=True, type="primary" if st.session_state.page == "support" else "secondary", key="sb_support"):
        st.session_state.page = "support"
        st.session_state.selected_product_id = None
        _reset_support_state()
        _reset_my_orders_state()
        st.rerun()

st.markdown("---")


# ===========================================================================
# SHOP PAGE
# ===========================================================================

if st.session_state.page == "shop":

    # -----------------------------------------------------------------------
    # Product details page
    # -----------------------------------------------------------------------

    if st.session_state.selected_product_id:

        product = _fetch_product(
            st.session_state.selected_product_id
        )

        if product is None:

            st.warning("Product not found.")

            if st.button(
                "← Back to Shop",
                key="btn_product_missing_back",
            ):
                st.session_state.selected_product_id = None
                st.rerun()

        else:

            if st.button(
                "← Back to Shop",
                key="btn_back_to_shop",
            ):
                st.session_state.selected_product_id = None
                st.rerun()

            st.markdown("## Product Details")

            st.markdown(
                f"### 🛍️ {product.name}"
            )

            if product.category:
                st.caption(product.category)

            st.markdown(
                f"## ₹{product.price:,.2f}"
            )

            st.markdown("---")

            info_col, support_col = st.columns([2, 1])

            with info_col:

                st.markdown("### 📋 Product Information")

                if product.category:
                    st.write(
                        f"**Category:** {product.category}"
                    )

                if product.store:
                    st.write(
                        f"**Store:** {product.store}"
                    )

                if product.stock > 0:
                    st.success(
                        f"✅ In Stock — {product.stock} available"
                    )

                else:
                    st.error(
                        "❌ Currently out of stock"
                    )

            with support_col:

                st.markdown("### 💬 Need Help?")

                st.write(
                    "Have a question about this product "
                    "or an existing order?"
                )

                if st.button(
                    "💬 Get Support",
                    type="primary",
                    use_container_width=True,
                    key=f"support_product_{product.product_id}",
                ):

                    st.session_state.result = None
                    st.session_state.original_request = ""
                    st.session_state.pending_input = (
                        f"I need help with {product.name}."
                    )

                    _reset_fmo_state()

                    st.session_state.page = "support"
                    st.session_state.selected_product_id = None

                    st.rerun()

            st.markdown("---")

            st.info(
                "Product information is loaded dynamically "
                "from the SupportFlow AI product catalog."
            )


    # -----------------------------------------------------------------------
    # Product catalog
    # -----------------------------------------------------------------------

    else:

        with st.container(border=True):
            st.markdown('<div id="shop-header-hook"></div>', unsafe_allow_html=True)
            st.markdown("## 🛍️ Product Catalog")
            st.caption(
                "Explore products and get AI-powered support when you need it."
            )

        products = _fetch_products()

        if not products:

            st.warning(
                "No products are available right now."
            )

        else:

            # ---------------------------------------------------------------
            # Search + category filter
            # ---------------------------------------------------------------

            with st.container(border=True):
                st.markdown('<div id="shop-search-hook"></div>', unsafe_allow_html=True)
                search_col, category_col = st.columns([2, 1])
                
                with search_col:
                    search_text = st.text_input(
                        "🔎 Search products",
                        placeholder="Search iPhone, laptop, headphones...",
                        key="product_search",
                    )
                
                categories = sorted(
                    {
                        product.category
                        for product in products
                        if product.category
                    }
                )
                
                with category_col:
                    selected_category = st.selectbox(
                        "📂 Category",
                        ["All Categories"] + categories,
                        key="product_category",
                    )

            # ---------------------------------------------------------------
            # Filtering
            # ---------------------------------------------------------------

            filtered_products = products

            if search_text.strip():

                query = search_text.strip().lower()

                filtered_products = [
                    product
                    for product in filtered_products
                    if (
                        query in product.name.lower()
                        or (
                            product.category
                            and query in product.category.lower()
                        )
                    )
                ]

            if selected_category != "All Categories":

                filtered_products = [
                    product
                    for product in filtered_products
                    if product.category == selected_category
                ]

            st.markdown("---")

            if not filtered_products:

                st.info(
                    "No products matched your search."
                )

            else:

                st.caption(
                    f"{len(filtered_products)} product(s) found"
                )

                # -----------------------------------------------------------
                # Product grid
                # -----------------------------------------------------------

                columns = st.columns(3)

                for index, product in enumerate(filtered_products):

                    with columns[index % 3]:

                        if render_product_card(product):

                            st.session_state.selected_product_id = (
                                product.product_id
                            )

                            st.rerun()


# ===========================================================================
# MY ORDERS PAGE
# ===========================================================================

elif st.session_state.page == "orders":

    with st.container(border=True):
        st.markdown('<div id="my-orders-hook"></div>', unsafe_allow_html=True)
        st.markdown("## 📦 My Orders")
        
        st.caption(
            "Enter your registered email to view your orders."
        )
        
        # -----------------------------------------------------------------------
        # Email input
        # -----------------------------------------------------------------------
        
        email_col, button_col = st.columns([3, 1])
        
        with email_col:
        
            order_email = st.text_input(
                "Registered Email",
                placeholder="Enter your registered email",
                value=st.session_state.get(
                    "my_orders_email",
                    "",
                ),
                key="my_orders_email_input",
            )
        
        with button_col:
        
            st.markdown("<br>", unsafe_allow_html=True)
        
            view_orders_clicked = st.button(
                "🔎 View My Orders",
                type="primary",
                use_container_width=True,
                key="view_my_orders",
            )

    # -----------------------------------------------------------------------
    # Fetch orders
    # -----------------------------------------------------------------------

    if view_orders_clicked:

        email = order_email.strip().lower()

        if not email:

            st.warning(
                "Please enter your registered email address."
            )

        else:

            with st.spinner(
                "Loading your orders..."
            ):

                try:

                    orders_result = _load_my_orders(email)

                    st.session_state.my_orders_email = email
                    st.session_state.my_orders_result = orders_result

                except Exception:

                    st.session_state.my_orders_result = None

                    st.error(
                        "Something went wrong while loading your orders. "
                        "Please try again."
                    )

    # -----------------------------------------------------------------------
    # Display orders
    # -----------------------------------------------------------------------

    orders_result = st.session_state.get(
        "my_orders_result"
    )

    if orders_result:

        if not orders_result.get("success"):

            st.error(
                orders_result.get(
                    "message",
                    "No account found.",
                )
            )

        else:

            customer_name = orders_result.get(
                "customer_name",
                "Customer",
            )

            orders = orders_result.get(
                "orders",
                [],
            )

            st.markdown("---")

            st.markdown(
                f"### 👋 Hi {customer_name}"
            )

            if not orders:

                st.info(
                    "No orders were found for this account."
                )

            else:

                st.caption(
                    f"{len(orders)} order(s) found"
                )

                st.markdown("")

                for order in orders:
                    _render_order_card(order)

    else:

        st.markdown("---")

        st.info(
            "Enter your registered email above to see your orders."
        )

        st.markdown("### 💬 Need help with an order?")

        if st.button(
            "Open AI Support",
            type="secondary",
            key="orders_open_support",
        ):

            _reset_support_state()

            st.session_state.page = "support"

            st.rerun()


# ===========================================================================
# SUPPORT PAGE
# ===========================================================================

elif st.session_state.page == "support":

    with st.container(border=True):
        st.markdown('<div id="ai-support-hook"></div>', unsafe_allow_html=True)
        st.markdown(
            """
            <div style="text-align: center;">
                <h2 style="font-weight: 700; margin-bottom: 0;"><span style="background: #E9D5FF; padding: 4px; border-radius: 8px;">🤖</span> AI Support Assistant</h2>
                <h4 style="color: #475569; margin-top: 0.5rem;">"How can we help you today?"</h4>
                <p style="color: #64748b; font-size: 0.95rem; margin-top: 0.5rem;">Describe your issue and SupportFlow AI will find the right resolution.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )

    # -----------------------------------------------------------------------
    # Consume pending input
    # -----------------------------------------------------------------------

    _pending = st.session_state.get(
        "pending_input",
        "",
    )

    if _pending:

        st.session_state.result = None
        st.session_state.original_request = ""
        st.session_state.pending_input = ""

        default_value = _pending

    else:

        default_value = ""

    # -----------------------------------------------------------------------
    # Demo scenarios
    # -----------------------------------------------------------------------

    st.markdown('<div id="ai-quick-actions-hook"></div>', unsafe_allow_html=True)
    selected_demo = render_examples()

    if selected_demo:

        st.session_state.pending_input = selected_demo
        st.session_state.result = None
        st.session_state.original_request = ""

        _reset_fmo_state()

        st.rerun()

    # -----------------------------------------------------------------------
    # Support input
    # -----------------------------------------------------------------------

    with st.container(border=True):
        st.markdown('<div id="ai-input-hook"></div>', unsafe_allow_html=True)
        user_message: str = st.text_area(
            label="Describe your issue",
            label_visibility="collapsed",
            value=default_value,
            height=150,
            placeholder=(
                "My payment was successful but my iPhone 15 "
                "order is still pending."
            ),
        )
    
        # -----------------------------------------------------------------------
        # Buttons
        # -----------------------------------------------------------------------
    
        col_resolve, col_clear = st.columns([3, 1])
    
        with col_resolve:
    
            resolve_clicked = st.button(
                "🔎 Resolve Issue",
                type="primary",
                use_container_width=True,
                key="support_resolve",
            )
    
        with col_clear:
    
            clear_clicked = st.button(
                "Clear",
                use_container_width=True,
                key="support_clear",
            )

    if clear_clicked:

        _reset_support_state()

        st.rerun()

    # -----------------------------------------------------------------------
    # Run coordinator
    # -----------------------------------------------------------------------

    if resolve_clicked:

        msg = user_message.strip()

        if not msg:

            st.warning(
                "Please describe your issue before clicking Resolve."
            )

        else:

            st.session_state.original_request = msg

            _reset_fmo_state()

            with st.spinner(
                "🤖 SupportFlow AI is analyzing your request...\n\n✓ Understanding your request\n✓ Checking relevant information\n✓ Preparing the best resolution"
            ):

                try:

                    st.session_state.result = run_coordinator(
                        msg
                    )

                except Exception:

                    st.session_state.result = None

                    st.error(
                        "Something went wrong. "
                        "Please try again or contact support."
                    )

    # -----------------------------------------------------------------------
    # Resolution
    # -----------------------------------------------------------------------

    if st.session_state.result:

        result = st.session_state.result

        response = result.get(
            "final_response",
            "",
        )

        resolved = result.get(
            "resolved",
            False,
        )

        # Safety net against raw None output

        if response and "None" in response:

            response = (
                "Please provide your order ID "
                "(for example, ORD005) so I can "
                "look into your request."
            )

            resolved = False

        st.markdown("---")

        missing = _needs_followup(
            result
        )

        # ===================================================================
        # Missing Order ID
        # ===================================================================

        if missing == "order_id":

            render_resolution(
                response,
                resolved,
                hide_clarification=True,
            )

            st.markdown("")

            selected_order_id = render_find_my_order(
                orders_result=st.session_state.get(
                    "fmo_orders_result"
                )
            )

            # ---------------------------------------------------------------
            # Find My Order selection
            # ---------------------------------------------------------------

            if selected_order_id:

                combined = (
                    f"{st.session_state.original_request} "
                    f"Order ID: {selected_order_id}"
                )

                _reset_fmo_state()

                with st.spinner(
                    "🔄 Checking your order…"
                ):

                    try:

                        st.session_state.result = (
                            run_coordinator(
                                combined
                            )
                        )

                    except Exception:

                        st.session_state.result = None

                        st.error(
                            "Something went wrong. "
                            "Please try again or contact support."
                        )

                new_result = st.session_state.result

                if (
                    new_result
                    and new_result.get("resolved")
                ):

                    st.session_state.original_request = ""

                st.rerun()

            # ---------------------------------------------------------------
            # Manual Order ID entry
            # ---------------------------------------------------------------

            _fmo_active = (
                st.session_state.get(
                    "fmo_show_email"
                )
                or st.session_state.get(
                    "fmo_orders_result"
                ) is not None
            )

            if not _fmo_active:

                st.markdown("---")

                st.markdown(
                    "**Or enter your Order ID directly:**"
                )

                raw_input = render_followup_input(
                    missing
                )

                if raw_input is not None:

                    ok, id_or_err = validate_order_id(
                        raw_input
                    )

                    if not ok:

                        st.warning(id_or_err)

                        st.stop()

                    combined = (
                        f"{st.session_state.original_request} "
                        f"Order ID: {id_or_err}"
                    )

                    with st.spinner(
                        "🔄 Checking your request…"
                    ):

                        try:

                            st.session_state.result = (
                                run_coordinator(
                                    combined
                                )
                            )

                        except Exception:

                            st.session_state.result = None

                            st.error(
                                "Something went wrong. "
                                "Please try again or contact support."
                            )

                    new_result = st.session_state.result

                    if (
                        new_result
                        and new_result.get("resolved")
                    ):

                        st.session_state.original_request = ""

                    st.rerun()

        # ===================================================================
        # Missing Customer ID
        # ===================================================================

        elif missing == "customer_id":

            render_resolution(
                response,
                resolved,
                hide_clarification=True,
            )

            st.markdown("---")

            raw_customer_id = render_followup_input(
                missing
            )

            if raw_customer_id is not None:

                ok, id_or_err = validate_customer_id(
                    raw_customer_id
                )

                if not ok:

                    st.warning(id_or_err)

                    st.stop()

                combined = (
                    f"{st.session_state.original_request} "
                    f"Customer ID: {id_or_err}"
                )

                with st.spinner(
                    "🔄 Checking your account…"
                ):

                    try:

                        st.session_state.result = (
                            run_coordinator(
                                combined
                            )
                        )

                    except Exception:

                        st.session_state.result = None

                        st.error(
                            "Something went wrong. "
                            "Please try again or contact support."
                        )

                new_result = st.session_state.result

                if (
                    new_result
                    and new_result.get("resolved")
                ):

                    st.session_state.original_request = ""

                st.rerun()

        # ===================================================================
        # Normal resolved / clarification response
        # ===================================================================

        else:

            render_resolution(
                response,
                resolved,
            )