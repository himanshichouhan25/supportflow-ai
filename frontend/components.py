# -*- coding: utf-8 -*-
"""
frontend/components.py -- Customer-facing UI components for SupportFlow AI.

Internal multi-agent workflow is completely hidden from the customer.

Components
----------
render_sidebar()            - sidebar with info/demo links
render_examples()           - quick-demo scenario buttons
validate_order_id()         - format-validate an order ID string
validate_customer_id()      - format-validate a customer ID string
render_followup_input()     - warning banner + ID text input + Continue button
render_find_my_order()      - full email to order-list to select flow
render_resolution()         - Resolution card (customer-facing only)
render_product_card()       - Product catalog card
"""

from __future__ import annotations

import re
import streamlit as st


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## 🧠 SupportFlow AI")
        st.markdown("**AI Customer Support Resolution Assistant**")
        st.caption("Describe your issue and get a support resolution.")
        st.markdown("---")

        st.markdown("#### Demo Scenarios")
        st.markdown(
            "- Payment & Order\n"
            "- Cancellation & Refund\n"
            "- Delivery Tracking"
        )

        st.markdown("---")

        st.markdown("#### Find My Order")
        st.markdown(
            "Don't know your order ID?  \n"
            "Enter your registered email and select your order."
        )

        st.markdown("---")

        st.caption(
            "Powered by\n"
            "FastAPI · PostgreSQL · Python · Gemini AI\n\n"
            "_Demo data only. Not affiliated with any real retailer._"
        )


# ---------------------------------------------------------------------------
# Example buttons
# ---------------------------------------------------------------------------

EXAMPLES: list[str] = [
    "My payment was successful but my iPhone 15 order ORD005 is still pending.",
    "Please cancel my order ORD007 and check whether I am eligible for a refund.",
    "Where is my package for order ORD009?",
]


_EXAMPLE_LABELS: list[str] = [
    "💳 Payment & Order",
    "❌ Cancel & Refund",
    "🚚 Delivery Tracking",
]


def render_examples() -> str | None:
    """
    Render clickable demo scenario buttons.

    Returns the example text when clicked, otherwise None.

    Clicking does NOT trigger the coordinator.
    """
    cols = st.columns(len(EXAMPLES))

    for col, label, example in zip(cols, _EXAMPLE_LABELS, EXAMPLES):
        with col:
            if st.button(
                label,
                use_container_width=True,
                key=f"ex_{label}",
            ):
                return example

    return None


# ---------------------------------------------------------------------------
# ID validation helpers
# ---------------------------------------------------------------------------

_ORDER_ID_RE = re.compile(r"^ORD\d+$", re.IGNORECASE)
_CUSTOMER_ID_RE = re.compile(r"^C\d+$", re.IGNORECASE)


def validate_order_id(raw: str) -> tuple[bool, str]:
    """Return (ok, normalised_id_or_error_message)."""

    val = raw.strip().upper()

    if not val:
        return False, "Please enter your order ID, for example ORD005."

    if not _ORDER_ID_RE.match(val):
        return (
            False,
            f"'{raw.strip()}' does not look like a valid order ID. "
            "Please use the format ORD005.",
        )

    return True, val


def validate_customer_id(raw: str) -> tuple[bool, str]:
    """Return (ok, normalised_id_or_error_message)."""

    val = raw.strip().upper()

    if not val:
        return False, "Please enter your customer ID, for example C101."

    if not _CUSTOMER_ID_RE.match(val):
        return (
            False,
            f"'{raw.strip()}' does not look like a valid customer ID. "
            "Please use the format C101.",
        )

    return True, val


# ---------------------------------------------------------------------------
# Follow-up input widget
# ---------------------------------------------------------------------------

def render_followup_input(missing: str) -> str | None:
    """
    Render a compact follow-up input for a missing order ID or customer ID.

    Returns the raw input string when Continue is clicked.
    """

    if missing == "order_id":
        label = "Order ID"
        placeholder = "e.g. ORD005"
        hint = "Please provide your order ID so I can continue."
    else:
        label = "Customer ID"
        placeholder = "e.g. C101"
        hint = "Please provide your customer ID so I can continue."

    st.warning("⚠️ More information needed")
    st.markdown(f"_{hint}_")

    followup_value = st.text_input(
        label=label,
        placeholder=placeholder,
        key=f"followup_{missing}",
    )

    if st.button(
        "➡️ Continue",
        type="primary",
        key="btn_continue",
    ):
        return followup_value

    return None


# ---------------------------------------------------------------------------
# Find My Order flow
# ---------------------------------------------------------------------------

_STATUS_BADGE: dict[str, str] = {
    "PENDING": "🟡 Pending",
    "CONFIRMED": "🔵 Confirmed",
    "SHIPPED": "📦 Shipped",
    "OUT_FOR_DELIVERY": "🚚 Out for delivery",
    "DELIVERED": "✅ Delivered",
    "CANCELLED": "❌ Cancelled",
}


def _product_emoji(product_name: str) -> str:
    """Return a best-match emoji for a product name."""

    lower = product_name.lower()

    if any(
        word in lower
        for word in ("iphone", "samsung", "galaxy", "phone")
    ):
        return "📱"

    if any(
        word in lower
        for word in ("laptop", "notebook", "vivobook", "macbook", "asus")
    ):
        return "💻"

    if any(
        word in lower
        for word in (
            "headphone",
            "earphone",
            "earbuds",
            "airpod",
            "wh-",
            "boat",
            "sony",
        )
    ):
        return "🎧"

    if any(
        word in lower
        for word in (
            "shoe",
            "sneaker",
            "air max",
            "footwear",
            "nike",
        )
    ):
        return "👟"

    if any(
        word in lower
        for word in ("mouse", "keyboard", "logitech")
    ):
        return "🖱️"

    if any(
        word in lower
        for word in ("book", "course", "edition", "python")
    ):
        return "📖"

    if any(
        word in lower
        for word in (
            "fryer",
            "oven",
            "blender",
            "philips",
            "mixer",
        )
    ):
        return "🍳"

    if any(
        word in lower
        for word in (
            "bulb",
            "lamp",
            "light",
            "led",
            "syska",
        )
    ):
        return "💡"

    return "🛒"


def _fmt_inr(amount: float) -> str:
    """Format an amount as INR."""

    try:
        return f"₹{int(amount):,}"
    except Exception:
        return str(amount)


def render_find_my_order(
    orders_result: dict | None,
) -> str | None:
    """
    Render the full 'Find My Order' flow.

    Flow:

        Email
          ↓
        Customer orders
          ↓
        Select order
          ↓
        Return internal order ID
    """

    # ------------------------------------------------------------------
    # Phase 0: offer Find My Order
    # ------------------------------------------------------------------

    if (
        not st.session_state.get("fmo_show_email")
        and orders_result is None
    ):
        st.warning("⚠️ We need a little more information")

        st.markdown(
            "Don’t know your order ID? We can find it for you."
        )

        if st.button(
            "🔍 Find My Order",
            type="secondary",
            key="btn_find_my_order",
        ):
            st.session_state.fmo_show_email = True
            st.session_state.fmo_orders_result = None
            st.session_state.fmo_selected_id = None
            st.rerun()

        return None

    # ------------------------------------------------------------------
    # Phase 1: email input
    # ------------------------------------------------------------------

    if (
        st.session_state.get("fmo_show_email")
        and st.session_state.get("fmo_orders_result") is None
    ):
        st.markdown("#### 📧 Enter your registered email address")

        email_val = st.text_input(
            label="Email address",
            placeholder="your-email@example.com",
            key="fmo_email_input",
        )

        col_find, col_back = st.columns([2, 1])

        with col_find:
            find_clicked = st.button(
                "🔍 Find My Orders",
                type="primary",
                key="btn_find_my_orders",
                use_container_width=True,
            )

        with col_back:
            if st.button(
                "Back",
                key="btn_fmo_back",
                use_container_width=True,
            ):
                st.session_state.fmo_show_email = False
                st.session_state.fmo_orders_result = None
                st.rerun()

        if find_clicked:
            raw_email = email_val.strip()

            if not raw_email:
                st.warning("Please enter your email address.")

            elif "@" not in raw_email:
                st.warning("Please enter a valid email address.")

            else:
                from tools.order_tool import find_orders_by_email
                from backend.database import SessionLocal

                db = SessionLocal()

                try:
                    result = find_orders_by_email(
                        raw_email,
                        db,
                    )
                finally:
                    db.close()

                st.session_state.fmo_orders_result = result
                st.rerun()

        return None

    # ------------------------------------------------------------------
    # Phase 2: order list
    # ------------------------------------------------------------------

    result = st.session_state.get("fmo_orders_result")

    if result is None:
        return None

    if not result.get("success"):
        st.error(
            result.get(
                "message",
                "We could not find your account. "
                "Please check the email and try again.",
            )
        )

        if st.button(
            "Try a different email",
            key="btn_fmo_retry",
        ):
            st.session_state.fmo_orders_result = None
            st.rerun()

        return None

    orders = result.get("orders", [])
    customer_name = result.get("customer_name", "")

    if not orders:
        st.info(
            f"We found your account"
            f"{', ' + customer_name if customer_name else ''}, "
            "but there are no orders available to display."
        )

        if st.button(
            "Try a different email",
            key="btn_fmo_retry_empty",
        ):
            st.session_state.fmo_orders_result = None
            st.session_state.fmo_show_email = False
            st.rerun()

        return None

    # ------------------------------------------------------------------
    # Display order cards
    # ------------------------------------------------------------------

    greeting = (
        f"Hi **{customer_name}**! "
        if customer_name
        else ""
    )

    st.markdown("#### 🛒 Your Orders")
    st.markdown(
        f"{greeting}"
        "Please select the order you need help with:"
    )

    for i, order in enumerate(orders):

        order_id = order["order_id"]
        product_name = order["product_name"]
        status = order["status"]
        amount = order["total_amount"]
        order_date = order.get("order_date", "")

        emoji = _product_emoji(product_name)
        badge = _STATUS_BADGE.get(status, status)
        amount_str = _fmt_inr(amount)

        date_str = (
            f" · Ordered {order_date}"
            if order_date
            else ""
        )

        with st.container(border=True):

            col_info, col_btn = st.columns([3, 1])

            with col_info:
                st.markdown(
                    f"**{emoji} {product_name}**"
                )

                st.markdown(
                    f"Status: {badge}"
                )

                st.markdown(
                    f"Amount: {amount_str}{date_str}"
                )

            with col_btn:
                if st.button(
                    "Select This Order",
                    key=f"btn_sel_{i}_{order_id}",
                    type="primary",
                    use_container_width=True,
                ):
                    return order_id

    if st.button(
        "Use a different email",
        key="btn_fmo_change",
    ):
        st.session_state.fmo_orders_result = None
        st.session_state.fmo_show_email = False
        st.rerun()

    return None


# ---------------------------------------------------------------------------
# Product Catalog
# ---------------------------------------------------------------------------

def render_product_card(product) -> bool:
    """
    Render a customer-facing product card.

    The product object is expected to come from the existing
    PostgreSQL Product SQLAlchemy model.

    Returns:
        True  -> customer clicked View Product
        False -> no selection
    """

    with st.container(border=True):

        emoji = _product_emoji(product.name)

        st.markdown(
            f"### {emoji} {product.name}"
        )

        if product.category:
            st.caption(product.category)

        st.markdown(
            f"### ₹{product.price:,.2f}"
        )

        return st.button(
            "View Product",
            key=f"view_product_{product.product_id}",
            use_container_width=True,
        )


# ---------------------------------------------------------------------------
# Resolution display
# ---------------------------------------------------------------------------

def render_resolution(
    final_response: str,
    resolved: bool,
    hide_clarification: bool = False,
) -> None:
    """
    Display the customer-facing resolution.

    No agent names, tool names, workflow steps,
    or internal data are shown.
    """

    st.markdown("### 🎯 Resolution")

    if hide_clarification:
        return

    if resolved:
        st.success("✅ Resolved")

    else:
        st.warning(
            "⚠️ Unable to fully resolve — "
            "please contact support for further assistance."
        )

    with st.container(border=True):
        st.markdown(final_response)