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
    render_sidebar,
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


# ---------------------------------------------------------------------------
# Custom styling
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    .product-price {
        font-size: 1.6rem;
        font-weight: 700;
    }

    .product-meta {
        color: #a0a0aa;
        font-size: 0.95rem;
    }

    .order-card {
        padding: 1rem;
        border-radius: 14px;
        border: 1px solid rgba(128, 128, 128, 0.25);
        margin-bottom: 1rem;
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
            st.markdown(f"### 🛍️ {product_name}")
            st.caption(f"Order ID: **{order_id}**")

        with top_right:
            st.markdown(
                f"### ₹{float(amount):,.2f}"
            )

        st.markdown("---")

        info_1, info_2, info_3 = st.columns(3)

        with info_1:
            st.markdown("**Order Status**")

            if order_status == "DELIVERED":
                st.success(f"✅ {order_status}")
            elif order_status == "CANCELLED":
                st.error(f"❌ {order_status}")
            elif order_status == "PENDING":
                st.warning(f"⏳ {order_status}")
            else:
                st.info(f"📦 {order_status}")

        with info_2:
            st.markdown("**Payment**")

            if payment_status == "SUCCESS":
                st.success(f"💳 {payment_status}")
            elif payment_status == "FAILED":
                st.error(f"❌ {payment_status}")
            elif payment_status == "REFUNDED":
                st.info(f"↩️ {payment_status}")
            elif payment_status == "PENDING":
                st.warning(f"⏳ {payment_status}")
            else:
                st.caption("Not available")

        with info_3:
            st.markdown("**Delivery**")

            if delivery_status == "DELIVERED":
                st.success(f"🚚 {delivery_status}")
            elif delivery_status == "DELAYED":
                st.warning(f"⚠️ {delivery_status}")
            elif delivery_status == "SHIPPED":
                st.info(f"🚚 {delivery_status}")
            elif delivery_status == "OUT_FOR_DELIVERY":
                st.info(f"📍 {delivery_status}")
            elif delivery_status == "PENDING":
                st.warning(f"⏳ {delivery_status}")
            else:
                st.caption("Not available")

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

st.markdown("# 🧠 SupportFlow AI")
st.caption("Smart shopping support powered by AI")


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

nav_shop, nav_orders, nav_support = st.columns(3)

with nav_shop:
    if st.button(
        "🛍️ Shop",
        use_container_width=True,
        type="primary" if st.session_state.page == "shop" else "secondary",
    ):
        st.session_state.page = "shop"

        st.session_state.selected_product_id = None

        _reset_support_state()
        _reset_my_orders_state()

        st.rerun()


with nav_orders:
    if st.button(
        "📦 My Orders",
        use_container_width=True,
        type="primary" if st.session_state.page == "orders" else "secondary",
    ):
        st.session_state.page = "orders"
        st.session_state.selected_product_id = None

        _reset_support_state()

        st.rerun()


with nav_support:
    if st.button(
        "💬 AI Support",
        use_container_width=True,
        type="primary" if st.session_state.page == "support" else "secondary",
    ):
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

    st.markdown("## 🎧 How can we help you?")

    st.caption(
        "Describe your issue and SupportFlow AI will help resolve it."
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
                "Resolving your issue…"
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