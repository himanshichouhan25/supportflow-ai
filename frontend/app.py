# -*- coding: utf-8 -*-
"""
frontend/app.py — SupportFlow AI Customer Support Platform (Task 13 UI/UX).

Run from project root:
    .venv\Scripts\streamlit.exe run frontend/app.py

Backend integration: FastAPI (/api/support/resolve, /api/products, /api/orders, /api/tickets, /api/dashboard/metrics).
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uuid
from types import SimpleNamespace
import streamlit as st

from frontend.api.support_api import resolve_support
from frontend.api.data_api import (
    fetch_products,
    fetch_orders,
    fetch_tickets,
    fetch_dashboard_metrics,
)

from frontend.components import (
    render_examples,
    render_find_my_order,
    render_followup_input,
    render_product_card,
    render_resolution,
    render_status_badge,
    render_support_context,
    render_workflow_activity_panel,
    render_agent_activity_panel,
    render_empty_state,
    render_error_state,
    validate_customer_id,
    validate_order_id,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="SupportFlow AI — Intelligent Customer Resolution",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "custom_sidebar_open" not in st.session_state:
    st.session_state.custom_sidebar_open = True


# ---------------------------------------------------------------------------
# Custom Styling System
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    :root {
        --primary-color: #5146C7;
        --primary-dark: #4338A8;
        --bg-main: #FAF9F6;
        --border-color: #E2E8F0;
        --sidebar-bg: #E9E7F8;
    }
    
    [data-testid="stAppViewContainer"] {
        background-color: var(--bg-main) !important;
    }
    [data-testid="stSidebar"] {
        background-color: var(--sidebar-bg) !important;
        border-right: 1px solid #D9D7EA !important;
    }
    
    .block-container {
        padding-top: 1.25rem;
        padding-bottom: 4rem;
        max-width: 1080px;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    header[data-testid="stHeader"] {
        background: transparent !important;
        box-shadow: none !important;
    }
    [data-testid="stToolbar"], .stAppDeployButton {
        visibility: hidden !important;
    }
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="stSidebarCollapseButton"] {
        display: none !important;
    }

    /* Cards & Containers */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        background: #FFFFFF !important;
        border: 1px solid var(--border-color) !important;
        border-radius: 14px !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.02), 0 2px 4px -1px rgba(0, 0, 0, 0.02) !important;
        padding: 1.5rem !important;
    }
    
    /* Navigation Bar styling */
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 0.5rem !important;
        margin-bottom: 2rem !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03) !important;
    }
    div:has(> #main-nav-hook) + div[data-testid="stVerticalBlock"] button {
        width: 100% !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        padding: 0.5rem !important;
    }
    
    /* Primary Buttons */
    button[kind="primary"] {
        background: var(--primary-color) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px -1px rgba(81, 70, 199, 0.3) !important;
    }
    button[kind="primary"]:hover {
        background: var(--primary-dark) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
    }
    button[kind="primary"] p {
        color: #FFFFFF !important;
    }

    /* Secondary Buttons */
    button[kind="secondary"] {
        background: #FFFFFF !important;
        color: #334155 !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }
    button[kind="secondary"]:hover {
        background: #F8FAFC !important;
        color: #1E293B !important;
        border-color: #94A3B8 !important;
    }
    
    /* Text Inputs & Textarea */
    .stTextArea textarea, .stTextInput input {
        background: #FFFFFF !important;
        border: 1px solid #CBD5E1 !important;
        border-radius: 10px !important;
        color: #0F172A !important;
        font-size: 1rem !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 2px rgba(81, 70, 199, 0.2) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------

if "support_session_id" not in st.session_state or not st.session_state.support_session_id:
    st.session_state.support_session_id = str(uuid.uuid4())

_STATE_DEFAULTS = [
    ("page", "home"),
    ("result", None),
    ("original_request", ""),
    ("pending_input", ""),
    ("fmo_show_email", False),
    ("fmo_orders_result", None),
    ("fmo_selected_id", None),
    ("selected_product_id", None),
    ("my_orders_result", None),
    ("my_orders_email", ""),
    ("support_order_id", None),
    ("support_product_id", None),
    ("current_customer_id", "CUST001"),
]

for _key, _default in _STATE_DEFAULTS:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reset_fmo_state() -> None:
    st.session_state.fmo_show_email = False
    st.session_state.fmo_orders_result = None
    st.session_state.fmo_selected_id = None


def _reset_my_orders_state() -> None:
    st.session_state.my_orders_result = None
    st.session_state.my_orders_email = ""


def _reset_support_state() -> None:
    st.session_state.result = None
    st.session_state.original_request = ""
    st.session_state.pending_input = ""
    st.session_state.support_order_id = None
    st.session_state.support_product_id = None
    _reset_fmo_state()


def _new_conversation() -> None:
    st.session_state.support_session_id = str(uuid.uuid4())
    _reset_support_state()


def _needs_followup(result: dict | None) -> str | None:
    if result is None:
        return None
    if result.get("resolved"):
        return None
    return result.get("missing")


def _get_products_list() -> list[SimpleNamespace]:
    raw_products = fetch_products()
    return [SimpleNamespace(**p) for p in raw_products]


def _get_product_by_id(product_id: str) -> SimpleNamespace | None:
    products = _get_products_list()
    for p in products:
        if getattr(p, "product_id", None) == product_id:
            return p
    return None


# ---------------------------------------------------------------------------
# Header Branding
# ---------------------------------------------------------------------------

st.markdown(
    """
    <div style="background: linear-gradient(135deg, #EEF2FF 0%, #E0E7FF 100%); padding: 1.75rem; border-radius: 16px; text-align: center; margin-bottom: 1.25rem; border: 1px solid #C7D2FE;">
        <h2 style="color: #1E1B4B; font-weight: 900; margin-bottom: 0; font-size: 2rem;">🧠 SupportFlow AI</h2>
        <p style="color: #4338CA; font-size: 1rem; margin-top: 0.25rem; font-weight: 500;">Agentic Customer Support & Automated Resolution Platform</p>
    </div>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------------------------------
# Top Primary Navigation
# ---------------------------------------------------------------------------

st.markdown('<div id="main-nav-hook"></div>', unsafe_allow_html=True)
nav_container = st.container()
with nav_container:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        if st.button("🏠 Home", use_container_width=True, type="primary" if st.session_state.page == "home" else "secondary", key="nav_home"):
            st.session_state.page = "home"
            st.rerun()

    with c2:
        if st.button("🛍️ Shop", use_container_width=True, type="primary" if st.session_state.page == "shop" else "secondary", key="nav_shop"):
            st.session_state.page = "shop"
            st.session_state.selected_product_id = None
            st.rerun()

    with c3:
        if st.button("📦 My Orders", use_container_width=True, type="primary" if st.session_state.page == "orders" else "secondary", key="nav_orders"):
            st.session_state.page = "orders"
            st.rerun()

    with c4:
        if st.button("💬 AI Support", use_container_width=True, type="primary" if st.session_state.page == "support" else "secondary", key="nav_support"):
            st.session_state.page = "support"
            st.rerun()

    with c5:
        if st.button("🎫 Tickets", use_container_width=True, type="primary" if st.session_state.page == "tickets" else "secondary", key="nav_tickets"):
            st.session_state.page = "tickets"
            st.rerun()

    with c6:
        if st.button("📊 Dashboard", use_container_width=True, type="primary" if st.session_state.page == "dashboard" else "secondary", key="nav_dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()


# ---------------------------------------------------------------------------
# Sidebar Navigation & Session Control
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🧠 SupportFlow AI")
    st.caption("FastAPI ↔ Streamlit Integration")
    st.markdown("---")

    if st.button("🏠 Home", use_container_width=True, type="primary" if st.session_state.page == "home" else "secondary", key="sb_home"):
        st.session_state.page = "home"
        st.rerun()

    if st.button("🛍️ Shop Catalog", use_container_width=True, type="primary" if st.session_state.page == "shop" else "secondary", key="sb_shop"):
        st.session_state.page = "shop"
        st.session_state.selected_product_id = None
        st.rerun()

    if st.button("📦 My Orders", use_container_width=True, type="primary" if st.session_state.page == "orders" else "secondary", key="sb_orders"):
        st.session_state.page = "orders"
        st.rerun()

    if st.button("💬 AI Support", use_container_width=True, type="primary" if st.session_state.page == "support" else "secondary", key="sb_support"):
        st.session_state.page = "support"
        st.rerun()

    if st.button("🎫 Support Tickets", use_container_width=True, type="primary" if st.session_state.page == "tickets" else "secondary", key="sb_tickets"):
        st.session_state.page = "tickets"
        st.rerun()

    if st.button("📊 Support Dashboard", use_container_width=True, type="primary" if st.session_state.page == "dashboard" else "secondary", key="sb_dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.markdown("---")
    st.markdown("#### 🔑 Active Session")
    st.code(st.session_state.support_session_id[:13] + "...", language="text")
    if st.button("➕ New Conversation", key="sb_new_conv", use_container_width=True):
        _new_conversation()
        st.rerun()


# ===========================================================================
# LANDING PAGE (HOME)
# ===========================================================================

if st.session_state.page == "home":

    with st.container(border=True):
        st.markdown(
            """
            <div style="text-align: center; padding: 2rem 1rem;">
                <h1 style="color: #0F172A; font-weight: 900; font-size: 2.75rem; margin-bottom: 0.5rem; letter-spacing: -0.03em;">
                    SUPPORTFLOW AI
                </h1>
                <h3 style="color: #5146C7; font-weight: 700; margin-top: 0; margin-bottom: 1rem;">
                    "Intelligent Support. Faster Resolution."
                </h3>
                <p style="color: #475569; font-size: 1.1rem; max-width: 700px; margin: 0 auto 2rem auto; line-height: 1.6;">
                    AI-powered customer support that understands your issue, checks policy and order data,
                    executes the right resolution, verifies the result, and escalates when needed.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        cta1, cta2 = st.columns([1, 1])
        with cta1:
            if st.button("🛍️ Shop Products", type="primary", use_container_width=True, key="landing_cta_shop"):
                st.session_state.page = "shop"
                st.rerun()
        with cta2:
            if st.button("💬 Get AI Support", type="secondary", use_container_width=True, key="landing_cta_support"):
                st.session_state.page = "support"
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("### ⚡ System Capabilities")

    f1, f2, f3 = st.columns(3)
    with f1:
        with st.container(border=True):
            st.markdown("#### 🧠 AI-Powered Support")
            st.caption("Understands complex intent, resolves context across multi-turn follow-ups, and answers questions accurately.")
    with f2:
        with st.container(border=True):
            st.markdown("#### 📜 Policy-Aware Decisions")
            st.caption("Retrieves relevant company support policies dynamically before proposing or taking action.")
    with f3:
        with st.container(border=True):
            st.markdown("#### ⚡ Multi-Step Resolution")
            st.caption("Executes complex workflows in dependency order with automated replanning on failure.")

    f4, f5 = st.columns(2)
    with f4:
        with st.container(border=True):
            st.markdown("#### 🛡️ Verified Actions")
            st.caption("Performs post-action transactional verification against PostgreSQL before reporting resolution.")
    with f5:
        with st.container(border=True):
            st.markdown("#### 🚨 Smart Escalation")
            st.caption("Creates structured support tickets with full context when requests cannot be automatically resolved.")


# ===========================================================================
# SHOP PAGE
# ===========================================================================

elif st.session_state.page == "shop":

    if st.session_state.selected_product_id:
        product = _get_product_by_id(st.session_state.selected_product_id)

        if product is None:
            render_empty_state("Product Not Found", "The requested product ID was not found in the catalog.", "🔍")
            if st.button("← Back to Shop Catalog", key="btn_product_missing_back"):
                st.session_state.selected_product_id = None
                st.rerun()
        else:
            if st.button("← Back to Shop Catalog", key="btn_back_to_shop"):
                st.session_state.selected_product_id = None
                st.rerun()

            st.markdown("## 🛍️ Product Details")

            with st.container(border=True):
                info_col, support_col = st.columns([2, 1])

                with info_col:
                    st.markdown(f"### {getattr(product, 'name', 'Product')}")
                    st.caption(f"Category: {getattr(product, 'category', 'General')} | Product ID: `{getattr(product, 'product_id', '')}`")
                    st.markdown(f"## ₹{float(getattr(product, 'price', 0)):,.2f}")
                    
                    stock = getattr(product, "stock", 0)
                    if stock > 0:
                        st.success(f"✅ In Stock — {stock} units available")
                    else:
                        st.error("❌ Out of Stock")

                    st.markdown(f"**Store:** `{getattr(product, 'store', 'Main Electronics Warehouse')}`")

                with support_col:
                    st.markdown("### 💬 Need Support?")
                    st.write("Have a question about this product or an existing order?")

                    if st.button(
                        "💬 Get Support",
                        type="primary",
                        use_container_width=True,
                        key=f"support_product_{product.product_id}",
                    ):
                        _reset_support_state()
                        st.session_state.support_product_id = product.product_id
                        st.session_state.pending_input = f"I need help with {product.name}."
                        st.session_state.page = "support"
                        st.session_state.selected_product_id = None
                        st.rerun()

    else:
        with st.container(border=True):
            st.markdown("## 🛍️ Product Catalog")
            st.caption("Explore products and get instant AI support.")

        try:
            products = _get_products_list()
        except Exception as ex:
            products = []
            render_error_state("Failed to load products", f"Could not connect to FastAPI backend: {ex}")

        if products:
            with st.container(border=True):
                search_col, category_col = st.columns([2, 1])
                with search_col:
                    search_text = st.text_input("🔎 Search products", placeholder="Search iPhone, laptop, headphones...", key="product_search")
                
                categories = sorted({p.category for p in products if getattr(p, "category", None)})
                with category_col:
                    selected_category = st.selectbox("📂 Category", ["All Categories"] + categories, key="product_category")

            filtered_products = products
            if search_text.strip():
                query = search_text.strip().lower()
                filtered_products = [
                    p for p in filtered_products
                    if (query in p.name.lower() or (getattr(p, "category", None) and query in p.category.lower()))
                ]

            if selected_category != "All Categories":
                filtered_products = [
                    p for p in filtered_products
                    if getattr(p, "category", None) == selected_category
                ]

            st.caption(f"{len(filtered_products)} product(s) found")

            if not filtered_products:
                render_empty_state("No Matching Products", "No products matched your search filter.", "🔎")
            else:
                columns = st.columns(3)
                for index, product in enumerate(filtered_products):
                    with columns[index % 3]:
                        if render_product_card(product):
                            st.session_state.selected_product_id = product.product_id
                            st.rerun()


# ===========================================================================
# MY ORDERS PAGE
# ===========================================================================

elif st.session_state.page == "orders":

    with st.container(border=True):
        st.markdown("## 📦 My Orders")
        st.caption("Enter your registered email to view your order history via FastAPI.")
        
        email_col, button_col = st.columns([3, 1])
        with email_col:
            order_email = st.text_input(
                "Registered Email",
                placeholder="e.g. aarav.sharma@example.com",
                value=st.session_state.get("my_orders_email", ""),
                key="my_orders_email_input",
            )
        with button_col:
            st.markdown("<br>", unsafe_allow_html=True)
            view_orders_clicked = st.button("🔎 View My Orders", type="primary", use_container_width=True, key="view_my_orders")

    if view_orders_clicked:
        email = order_email.strip().lower()
        if not email:
            st.warning("Please enter your registered email address.")
        else:
            with st.spinner("Loading orders from FastAPI backend..."):
                try:
                    orders_result = fetch_orders(email=email)
                    st.session_state.my_orders_email = email
                    st.session_state.my_orders_result = orders_result
                except Exception as ex:
                    st.session_state.my_orders_result = None
                    render_error_state("Failed to load orders", str(ex))

    orders_result = st.session_state.get("my_orders_result")

    if orders_result:
        if isinstance(orders_result, dict) and not orders_result.get("success", True):
            st.error(orders_result.get("message", "No account found."))
        else:
            if isinstance(orders_result, dict):
                customer_name = orders_result.get("customer_name", "Customer")
                orders = orders_result.get("orders", [])
            else:
                customer_name = "Customer"
                orders = orders_result

            st.markdown(f"### 👋 Orders for {customer_name}")

            if not orders:
                render_empty_state("No Orders Found", "There are no orders registered under this email account.", "📦")
            else:
                for order in orders:
                    order_id = order.get("order_id", "")
                    product_name = order.get("product_name", "Product")
                    amount = order.get("total_amount", 0)
                    order_status = order.get("status") or order.get("order_status", "UNKNOWN")
                    order_date = order.get("order_date", "")
                    payment_status = order.get("payment_status", "N/A")
                    delivery_status = order.get("delivery_status", "N/A")
                    tracking_number = order.get("tracking_number")

                    with st.container(border=True):
                        top_l, top_r = st.columns([3, 1])
                        with top_l:
                            st.markdown(f"#### 🛍️ {product_name}")
                            st.markdown(f"Order ID: `<strong>{order_id}</strong>`", unsafe_allow_html=True)
                        with top_r:
                            st.markdown(f"<h3 style='text-align: right; margin: 0;'>₹{float(amount):,.2f}</h3>", unsafe_allow_html=True)

                        i1, i2, i3 = st.columns(3)
                        with i1:
                            st.markdown("<small style='color: #64748B;'>Order Status</small>", unsafe_allow_html=True)
                            st.markdown(render_status_badge(order_status), unsafe_allow_html=True)
                        with i2:
                            st.markdown("<small style='color: #64748B;'>Payment</small>", unsafe_allow_html=True)
                            st.markdown(render_status_badge(payment_status), unsafe_allow_html=True)
                        with i3:
                            st.markdown("<small style='color: #64748B;'>Delivery</small>", unsafe_allow_html=True)
                            st.markdown(render_status_badge(delivery_status), unsafe_allow_html=True)

                        if order_date:
                            st.caption(f"📅 Ordered on {order_date}")

                        if tracking_number:
                            st.markdown(f"Tracking Number: `{tracking_number}`")

                        if st.button("💬 Get Support for this Order", key=f"order_support_{order_id}", use_container_width=True, type="primary"):
                            _reset_support_state()
                            st.session_state.support_order_id = order_id
                            st.session_state.pending_input = f"I need help with Order ID: {order_id}."
                            st.session_state.page = "support"
                            st.rerun()

    else:
        render_empty_state("Enter Email to View Orders", "Type your registered email above (e.g., aarav.sharma@example.com) to look up your orders.", "📧")


# ===========================================================================
# TICKETS PAGE
# ===========================================================================

elif st.session_state.page == "tickets":

    with st.container(border=True):
        st.markdown("## 🎫 Support Tickets")
        st.caption("Real-time support ticket records from PostgreSQL backend.")

    try:
        tickets = fetch_tickets()
    except Exception as ex:
        tickets = []
        render_error_state("Failed to load tickets", str(ex))

    if not tickets:
        render_empty_state("No Support Tickets", "You're all clear! No support tickets currently exist.", "🎫")
    else:
        st.caption(f"{len(tickets)} support ticket(s) found")
        for t in tickets:
            ticket_id = t.get("ticket_id", "N/A")
            customer_id = t.get("customer_id", "N/A")
            order_id = t.get("order_id", "N/A")
            category = t.get("category", "GENERAL")
            priority = t.get("priority", "MEDIUM")
            status_val = t.get("status", "OPEN")
            reason = t.get("reason", "No reason provided")
            next_step = t.get("recommended_next_step", "Under Review")
            created_at = t.get("created_at", "")

            with st.container(border=True):
                h1, h2 = st.columns([3, 1])
                with h1:
                    st.markdown(f"#### Ticket <code>{ticket_id}</code>", unsafe_allow_html=True)
                    st.markdown(f"**Customer:** `{customer_id}` | **Order:** `{order_id}` | **Category:** `{category}`")
                with h2:
                    st.markdown(f"**Status:** {render_status_badge(status_val)}", unsafe_allow_html=True)
                    st.markdown(f"**Priority:** {render_status_badge(priority)}", unsafe_allow_html=True)

                st.markdown(f"**Reason:** {reason}")
                if next_step:
                    st.info(f"**Recommended Next Step:** {next_step}")
                if created_at:
                    st.caption(f"Created: {created_at}")


# ===========================================================================
# DASHBOARD PAGE
# ===========================================================================

elif st.session_state.page == "dashboard":

    with st.container(border=True):
        st.markdown("## 📊 Operational Analytics Dashboard")
        st.caption("Live operational statistics retrieved directly from PostgreSQL via FastAPI.")

    try:
        metrics = fetch_dashboard_metrics()
    except Exception as ex:
        metrics = {}
        render_error_state("Failed to load metrics", str(ex))

    if metrics:
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Orders", metrics.get("total_orders", 0))
        with m2:
            st.metric("Open Tickets", metrics.get("open_tickets", 0))
        with m3:
            st.metric("Resolved Tickets", metrics.get("resolved_tickets", 0))
        with m4:
            st.metric("Escalated Tickets", metrics.get("escalated_tickets", 0))

        st.markdown("<br>", unsafe_allow_html=True)

        r1, r2, r3 = st.columns(3)
        with r1:
            st.metric("Total Refunds", metrics.get("refunds_count", 0))
        with r2:
            st.metric("Total Returns", metrics.get("returns_count", 0))
        with r3:
            st.metric("Total Replacements", metrics.get("replacements_count", 0))


# ===========================================================================
# AI SUPPORT PAGE
# ===========================================================================

elif st.session_state.page == "support":

    with st.container(border=True):
        st.markdown(
            f"""
            <div style="text-align: center;">
                <h2 style="font-weight: 800; margin-bottom: 0;"><span style="background: #E9D5FF; padding: 4px 10px; border-radius: 10px;">🤖</span> AI Support Assistant</h2>
                <p style="color: #475569; margin-top: 0.5rem;">Describe your issue and SupportFlow AI will find and execute the optimal resolution.</p>
            </div>
            """, 
            unsafe_allow_html=True
        )

    # Render Support Context if present
    render_support_context({
        "order_id": st.session_state.get("support_order_id"),
        "product_id": st.session_state.get("support_product_id"),
        "customer_id": st.session_state.get("current_customer_id"),
    })

    _pending = st.session_state.get("pending_input", "")
    if _pending:
        st.session_state.result = None
        st.session_state.original_request = ""
        st.session_state.pending_input = ""
        default_value = _pending
    else:
        default_value = ""

    selected_demo = render_examples()

    if selected_demo:
        st.session_state.pending_input = selected_demo
        st.session_state.result = None
        st.session_state.original_request = ""
        _reset_fmo_state()
        st.rerun()

    with st.container(border=True):
        user_message: str = st.text_area(
            label="Describe your issue",
            label_visibility="collapsed",
            value=default_value,
            height=130,
            placeholder="e.g. My product is damaged. I want a replacement for order ORD004.",
        )
    
        c_res, c_clr, c_new = st.columns([3, 1, 1])
        with c_res:
            resolve_clicked = st.button("🔎 Resolve Issue", type="primary", use_container_width=True, key="support_resolve")
        with c_clr:
            clear_clicked = st.button("Clear", use_container_width=True, key="support_clear")
        with c_new:
            new_conv_clicked = st.button("New Chat", use_container_width=True, key="support_new_chat")

    if clear_clicked:
        _reset_support_state()
        st.rerun()

    if new_conv_clicked:
        _new_conversation()
        st.rerun()

    if resolve_clicked:
        msg = user_message.strip()
        if not msg:
            st.warning("Please describe your issue before clicking Resolve.")
        else:
            st.session_state.original_request = msg
            _reset_fmo_state()

            with st.spinner("🤖 SupportFlow AI is processing your request via FastAPI backend..."):
                try:
                    res = resolve_support(
                        message=msg,
                        session_id=st.session_state.support_session_id,
                        customer_id=st.session_state.get("current_customer_id"),
                        order_id=st.session_state.get("support_order_id"),
                        product_id=st.session_state.get("support_product_id"),
                    )
                    st.session_state.result = res
                except Exception as ex:
                    st.session_state.result = None
                    render_error_state("FastAPI Call Failed", str(ex))

    if st.session_state.result:
        result = st.session_state.result
        response = result.get("final_response") or result.get("message") or ""
        resolved = result.get("resolved") or (result.get("final_status") == "RESOLVED")

        missing = _needs_followup(result)

        if missing == "order_id":
            render_resolution(response, resolved, hide_clarification=True)
            selected_order_id = render_find_my_order(orders_result=st.session_state.get("fmo_orders_result"))

            if selected_order_id:
                combined = f"{st.session_state.original_request} Order ID: {selected_order_id}"
                _reset_fmo_state()

                with st.spinner("🔄 Checking your order via FastAPI..."):
                    try:
                        res = resolve_support(
                            message=combined,
                            session_id=st.session_state.support_session_id,
                            customer_id=st.session_state.get("current_customer_id"),
                        )
                        st.session_state.result = res
                    except Exception as ex:
                        st.session_state.result = None
                        render_error_state("Error checking order", str(ex))

                new_result = st.session_state.result
                if new_result and (new_result.get("resolved") or new_result.get("final_status") == "RESOLVED"):
                    st.session_state.original_request = ""
                st.rerun()

            _fmo_active = st.session_state.get("fmo_show_email") or st.session_state.get("fmo_orders_result") is not None

            if not _fmo_active:
                st.markdown("**Or enter your Order ID directly:**")
                raw_input = render_followup_input(missing)

                if raw_input is not None:
                    ok, id_or_err = validate_order_id(raw_input)
                    if not ok:
                        st.warning(id_or_err)
                        st.stop()

                    combined = f"{st.session_state.original_request} Order ID: {id_or_err}"
                    with st.spinner("🔄 Checking your request via FastAPI..."):
                        try:
                            res = resolve_support(
                                message=combined,
                                session_id=st.session_state.support_session_id,
                                customer_id=st.session_state.get("current_customer_id"),
                            )
                            st.session_state.result = res
                        except Exception as ex:
                            st.session_state.result = None
                            render_error_state("Error checking request", str(ex))

                    new_result = st.session_state.result
                    if new_result and (new_result.get("resolved") or new_result.get("final_status") == "RESOLVED"):
                        st.session_state.original_request = ""
                    st.rerun()

        elif missing == "customer_id":
            render_resolution(response, resolved, hide_clarification=True)
            raw_customer_id = render_followup_input(missing)

            if raw_customer_id is not None:
                ok, id_or_err = validate_customer_id(raw_customer_id)
                if not ok:
                    st.warning(id_or_err)
                    st.stop()

                combined = f"{st.session_state.original_request} Customer ID: {id_or_err}"
                with st.spinner("🔄 Checking your account via FastAPI..."):
                    try:
                        res = resolve_support(
                            message=combined,
                            session_id=st.session_state.support_session_id,
                            customer_id=id_or_err,
                        )
                        st.session_state.result = res
                    except Exception as ex:
                        st.session_state.result = None
                        render_error_state("Error checking account", str(ex))

                new_result = st.session_state.result
                if new_result and (new_result.get("resolved") or new_result.get("final_status") == "RESOLVED"):
                    st.session_state.original_request = ""
                st.rerun()

        else:
            render_resolution(response, resolved)

        # Render Task 11/12 Activity Panels
        wf_trace = result.get("workflow_trace")
        wf_plan = result.get("workflow_plan")
        render_workflow_activity_panel(workflow_trace=wf_trace, workflow_plan=wf_plan)
        render_agent_activity_panel(result)