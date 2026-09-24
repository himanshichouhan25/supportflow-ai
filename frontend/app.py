# -*- coding: utf-8 -*-
"""
frontend/app.py -- SupportFlow AI customer-facing Streamlit app.

SupportFlow AI is a fictional e-commerce storefront with
AI-powered customer support.

Main sections:
    🏠 Shop
    📦 My Orders
    🎧 Support

The internal multi-agent architecture is never shown to customers.
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------

import streamlit as st
from sqlalchemy import select


# ---------------------------------------------------------------------------
# Project imports
# ---------------------------------------------------------------------------

from backend.database import SessionLocal
from backend.models.product import Product

from agents.coordinator import run_coordinator

from frontend.components import (
    EXAMPLES,
    render_examples,
    render_find_my_order,
    render_followup_input,
    render_product_card,
    render_resolution,
    render_sidebar,
    validate_order_id,
    validate_customer_id,
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


# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>

    .block-container {
        padding-top: 1.8rem;
        max-width: 1200px;
    }

    .store-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.2rem;
    }

    .store-subtitle {
        color: #9ca3af;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.6rem;
        font-weight: 700;
        margin-top: 1rem;
        margin-bottom: 1rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state defaults
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
]

for _key, _default in _STATE_DEFAULTS:
    if _key not in st.session_state:
        st.session_state[_key] = _default


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _reset_support_state() -> None:
    """Reset support-related session state."""

    st.session_state.result = None
    st.session_state.original_request = ""
    st.session_state.pending_input = ""

    st.session_state.fmo_show_email = False
    st.session_state.fmo_orders_result = None
    st.session_state.fmo_selected_id = None


def _reset_fmo_state() -> None:
    """Reset Find My Order state."""

    st.session_state.fmo_show_email = False
    st.session_state.fmo_orders_result = None
    st.session_state.fmo_selected_id = None


def _fetch_products() -> list[Product]:
    """
    Fetch all products from PostgreSQL.

    Product data is never hardcoded in the frontend.
    """

    db = SessionLocal()

    try:
        statement = (
            select(Product)
            .order_by(Product.name.asc())
        )

        return list(db.scalars(statement).all())

    finally:
        db.close()


def _needs_followup(result: dict | None) -> str | None:
    """
    Return the missing information type required by the coordinator.
    """

    if result is None:
        return None

    if result.get("resolved"):
        return None

    return result.get("missing")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

render_sidebar()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="store-title">🛍️ SupportFlow AI</div>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="store-subtitle">'
    "Shop products and get AI-powered customer support when you need it."
    "</div>",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Main navigation
# ---------------------------------------------------------------------------

nav_shop, nav_orders, nav_support = st.columns(3)

with nav_shop:
    if st.button(
        "🏠 Shop",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state.page == "shop"
            else "secondary"
        ),
        key="nav_shop",
    ):
        st.session_state.page = "shop"
        _reset_support_state()
        st.rerun()


with nav_orders:
    if st.button(
        "📦 My Orders",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state.page == "orders"
            else "secondary"
        ),
        key="nav_orders",
    ):
        st.session_state.page = "orders"
        _reset_support_state()
        st.rerun()


with nav_support:
    if st.button(
        "🎧 Support",
        use_container_width=True,
        type=(
            "primary"
            if st.session_state.page == "support"
            else "secondary"
        ),
        key="nav_support",
    ):
        st.session_state.page = "support"
        st.rerun()


st.markdown("---")


# ===========================================================================
# SHOP
# ===========================================================================

if st.session_state.page == "shop":

    st.markdown(
        '<div class="section-title">Discover Products</div>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Load products
    # -----------------------------------------------------------------------

    try:
        products = _fetch_products()

    except Exception as exc:
        st.error(
            "Unable to load products right now. "
            "Please make sure the database is running."
        )
        st.caption(f"Database error: {type(exc).__name__}")
        st.stop()

    # -----------------------------------------------------------------------
    # Empty database state
    # -----------------------------------------------------------------------

    if not products:
        st.info(
            "No products are available right now."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Search + category filter
    # -----------------------------------------------------------------------

    search_col, category_col = st.columns([2, 1])

    with search_col:
        search_text = st.text_input(
            "Search products",
            placeholder="🔎 Search by product name or category...",
            key="product_search",
        )

    # Build categories dynamically from database.
    categories = sorted(
        {
            product.category
            for product in products
            if product.category
        }
    )

    with category_col:
        category_options = ["All"] + categories

        selected_category = st.selectbox(
            "Category",
            options=category_options,
            key="product_category",
        )

    # -----------------------------------------------------------------------
    # Deterministic filtering
    # -----------------------------------------------------------------------

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

    if selected_category != "All":
        filtered_products = [
            product
            for product in filtered_products
            if product.category == selected_category
        ]

    # -----------------------------------------------------------------------
    # Results count
    # -----------------------------------------------------------------------

    st.caption(
        f"Showing {len(filtered_products)} "
        f"of {len(products)} products"
    )

    # -----------------------------------------------------------------------
    # No search results
    # -----------------------------------------------------------------------

    if not filtered_products:
        st.info(
            "No products found. Try another search or category."
        )
        st.stop()

    # -----------------------------------------------------------------------
    # Product grid
    # -----------------------------------------------------------------------

    columns = st.columns(3)

    for index, product in enumerate(filtered_products):

        with columns[index % 3]:

            selected = render_product_card(product)

            if selected:
                st.session_state.selected_product_id = (
                    product.product_id
                )

                st.session_state.selected_product_name = (
                    product.name
                )

                st.session_state.selected_product_price = (
                    product.price
                )

                st.session_state.selected_product_category = (
                    product.category
                )

                st.rerun()

    # -----------------------------------------------------------------------
    # Selected product
    # -----------------------------------------------------------------------

    selected_product_id = st.session_state.get(
        "selected_product_id"
    )

    if selected_product_id:

        selected_product = next(
            (
                product
                for product in products
                if product.product_id == selected_product_id
            ),
            None,
        )

        if selected_product:

            st.markdown("---")
            st.markdown("### 🛍️ Selected Product")

            with st.container(border=True):

                st.markdown(
                    f"## {selected_product.name}"
                )

                if selected_product.category:
                    st.caption(
                        selected_product.category
                    )

                st.markdown(
                    f"### ₹{selected_product.price:,.2f}"
                )

                if selected_product.store:
                    st.caption(
                        f"Store: {selected_product.store}"
                    )

                st.info(
                    "Product details page will be added next."
                )

                if st.button(
                    "🎧 Need help with this product?",
                    key="support_selected_product",
                    type="primary",
                ):
                    st.session_state.page = "support"

                    st.session_state.pending_input = (
                        f"I need help with "
                        f"{selected_product.name}."
                    )

                    st.rerun()


# ===========================================================================
# MY ORDERS
# ===========================================================================

elif st.session_state.page == "orders":

    st.markdown(
        '<div class="section-title">📦 My Orders</div>',
        unsafe_allow_html=True,
    )

    st.info(
        "My Orders is coming next. "
        "For now, you can use Support → Find My Order "
        "to locate an order using your registered email."
    )

    if st.button(
        "🎧 Go to Support",
        type="primary",
        key="orders_go_support",
    ):
        st.session_state.page = "support"
        st.rerun()


# ===========================================================================
# SUPPORT
# ===========================================================================

elif st.session_state.page == "support":

    st.markdown(
        '<div class="section-title">'
        "🎧 How can we help you?"
        "</div>",
        unsafe_allow_html=True,
    )

    st.caption(
        "Describe your issue and SupportFlow AI will help resolve it."
    )

    # -----------------------------------------------------------------------
    # Session state for pending demo input
    # -----------------------------------------------------------------------

    pending = st.session_state.get(
        "pending_input",
        "",
    )

    if pending:
        st.session_state.pending_input = ""
        default_value = pending

    else:
        default_value = ""

    # -----------------------------------------------------------------------
    # Demo scenarios
    # -----------------------------------------------------------------------

    selected_example = render_examples()

    if selected_example:

        st.session_state.pending_input = selected_example
        st.session_state.result = None
        st.session_state.original_request = ""

        _reset_fmo_state()

        st.rerun()

    # -----------------------------------------------------------------------
    # Issue input
    # -----------------------------------------------------------------------

    user_message: str = st.text_area(
        label="Describe your issue",
        label_visibility="collapsed",
        value=default_value,
        height=130,
        placeholder=(
            "Example: My payment was successful "
            "but my order is still pending."
        ),
        key="support_message",
    )

    col_resolve, col_clear = st.columns([3, 1])

    with col_resolve:

        resolve_clicked = st.button(
            "🔍 Resolve Issue",
            type="primary",
            use_container_width=True,
            key="resolve_issue",
        )

    with col_clear:

        if st.button(
            "Clear",
            use_container_width=True,
            key="clear_support",
        ):
            _reset_support_state()

            if "support_message" in st.session_state:
                del st.session_state["support_message"]

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
                "Resolving your issue..."
            ):

                try:

                    st.session_state.result = (
                        run_coordinator(msg)
                    )

                except Exception:

                    st.session_state.result = None

                    st.error(
                        "Something went wrong. "
                        "Please try again or contact support."
                    )

    # -----------------------------------------------------------------------
    # Display resolution
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

        # Safety net: never display raw None.
        if response and "None" in response:

            response = (
                "Please provide your order ID "
                "(for example, ORD005) so I can "
                "look into your request."
            )

            resolved = False

        st.markdown("---")

        missing = _needs_followup(result)

        # ===============================================================
        # Missing Order ID
        # ===============================================================

        if missing == "order_id":

            render_resolution(
                response,
                resolved,
                hide_clarification=True,
            )

            st.markdown("")

            selected_order_id = render_find_my_order(
                orders_result=(
                    st.session_state.get(
                        "fmo_orders_result"
                    )
                )
            )

            # -----------------------------------------------------------
            # Customer selected an order
            # -----------------------------------------------------------

            if selected_order_id:

                combined = (
                    f"{st.session_state.original_request} "
                    f"Order ID: {selected_order_id}"
                )

                _reset_fmo_state()

                with st.spinner(
                    "🔄 Checking your order..."
                ):

                    try:

                        st.session_state.result = (
                            run_coordinator(combined)
                        )

                    except Exception:

                        st.session_state.result = None

                        st.error(
                            "Something went wrong. "
                            "Please try again or contact support."
                        )

                new_result = st.session_state.result

                if new_result and new_result.get(
                    "resolved"
                ):
                    st.session_state.original_request = ""

                st.rerun()

            # -----------------------------------------------------------
            # Manual Order ID
            # -----------------------------------------------------------

            fmo_active = (
                st.session_state.get(
                    "fmo_show_email"
                )
                or st.session_state.get(
                    "fmo_orders_result"
                ) is not None
            )

            if not fmo_active:

                st.markdown("---")

                st.markdown(
                    "**Or enter your Order ID directly:**"
                )

                raw_input = render_followup_input(
                    missing
                )

                if raw_input is not None:

                    ok, id_or_error = (
                        validate_order_id(raw_input)
                    )

                    if not ok:

                        st.warning(id_or_error)
                        st.stop()

                    combined = (
                        f"{st.session_state.original_request} "
                        f"Order ID: {id_or_error}"
                    )

                    with st.spinner(
                        "🔄 Checking your request..."
                    ):

                        try:

                            st.session_state.result = (
                                run_coordinator(combined)
                            )

                        except Exception:

                            st.session_state.result = None

                            st.error(
                                "Something went wrong. "
                                "Please try again or contact support."
                            )

                    new_result = (
                        st.session_state.result
                    )

                    if new_result and new_result.get(
                        "resolved"
                    ):
                        st.session_state.original_request = ""

                    st.rerun()

        # ===============================================================
        # Missing Customer ID
        # ===============================================================

        elif missing == "customer_id":

            render_resolution(
                response,
                resolved,
                hide_clarification=True,
            )

            st.markdown("")

            raw_input = render_followup_input(
                missing
            )

            if raw_input is not None:

                ok, id_or_error = (
                    validate_customer_id(raw_input)
                )

                if not ok:

                    st.warning(id_or_error)
                    st.stop()

                combined = (
                    f"{st.session_state.original_request} "
                    f"Customer ID: {id_or_error}"
                )

                with st.spinner(
                    "🔄 Checking your request..."
                ):

                    try:

                        st.session_state.result = (
                            run_coordinator(combined)
                        )

                    except Exception:

                        st.session_state.result = None

                        st.error(
                            "Something went wrong. "
                            "Please try again or contact support."
                        )

                new_result = (
                    st.session_state.result
                )

                if new_result and new_result.get(
                    "resolved"
                ):
                    st.session_state.original_request = ""

                st.rerun()

        # ===============================================================
        # Normal resolution
        # ===============================================================

        else:

            render_resolution(
                response,
                resolved,
            )