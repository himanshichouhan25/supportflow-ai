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
        def get_html_badge(status):
            s = status.upper()
            if s in ['SUCCESS', 'RESOLVED']: return f"<span style='background:#DCFCE7; color:#166534; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['DELIVERED']: return f"<span style='background:#EAF8EF; color:#166534; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['PENDING', 'DELAYED']: return f"<span style='background:#FFF7D6; color:#92400E; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['FAILED']: return f"<span style='background:#FEECEC; color:#B91C1C; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['CANCELLED', 'REFUNDED']: return f"<span style='background:#F1F5F9; color:#475569; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['SHIPPED', 'OUT_FOR_DELIVERY', 'CONFIRMED']: return f"<span style='background:#E8F1FF; color:#1D4ED8; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            if s in ['OPEN']: return f"<span style='background:#EDE9FE; color:#6B21A8; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"
            return f"<span style='background:#E8F1FF; color:#1D4ED8; padding:0.2rem 0.6rem; border-radius:9999px; font-size:0.75rem; font-weight:600;'>{status}</span>"

        badge_html = get_html_badge(status)
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
                    f"<div style='margin: 4px 0;'>{badge_html}</div>",
                    unsafe_allow_html=True
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

import os
import base64

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

def _get_category_color(category: str) -> str:
    cat = category.lower() if category else ""
    if "smartphone" in cat or "phone" in cat: return "#E8F1FF"
    if "laptop" in cat or "computer" in cat: return "#F3E8FF"
    if "audio" in cat or "headphone" in cat: return "#F0E9FF"
    if "accessor" in cat: return "#E8F8F1"
    if "footwear" in cat or "shoe" in cat: return "#FFEFE5"
    if "kitchen" in cat or "appliance" in cat: return "#FFF9E5"
    if "book" in cat: return "#FCEFF5"
    return "#F8F9FA"

def render_product_card(product) -> bool:
    """
    Render a customer-facing product card.
    """
    with st.container(border=True):
        image_url = _get_image_data_uri(product.name)
        bg_color = _get_category_color(product.category)
        
        # Product Image area
        if image_url:
            st.markdown(
                f'''
                <div style="background-color: {bg_color}; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; text-align: center; display: flex; align-items: center; justify-content: center; height: 180px;">
                    <img src="{image_url}" alt="{product.name}" style="max-height: 100%; max-width: 100%; object-fit: contain; border-radius: 8px;" onerror="this.onerror=null; this.parentElement.innerHTML='<div style=\\'display:flex; flex-direction:column; align-items:center;\\'><div style=\\'font-size: 2.5rem;\\'>📦</div><div style=\\'color: #64748B; font-size: 0.85rem; margin-top: 0.5rem;\\'>Product image unavailable</div></div>';">
                </div>
                ''',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                f'''
                <div style="background-color: {bg_color}; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 180px;">
                    <div style="font-size: 2.5rem;">📦</div>
                    <div style="color: #64748B; font-size: 0.85rem; margin-top: 0.5rem;">Product image unavailable</div>
                </div>
                ''',
                unsafe_allow_html=True
            )
        
        emoji = _product_emoji(product.name)
        st.markdown(f"#### {emoji} {product.name}", unsafe_allow_html=True)
        if product.category:
            st.markdown(f"<p style='color: #64748b; font-size: 0.85rem; margin-top: -10px;'>{product.category}</p>", unsafe_allow_html=True)
        st.markdown(f"<h3 style='color: #172033; margin-top: 10px; margin-bottom: 20px;'>₹{product.price:,.2f}</h3>", unsafe_allow_html=True)

        return st.button(
            "View Details",
            key=f"view_product_{product.product_id}",
            use_container_width=True,
            type="primary"
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
    Display the customer-facing resolution in a premium card.
    """

    if hide_clarification:
        return

    st.markdown("### 🎯 Resolution")

    with st.container(border=True):
        st.markdown('<div id="resolution-hook"></div>', unsafe_allow_html=True)
        if resolved:
            st.markdown(
                """
                <div style='display: flex; align-items: center; margin-bottom: 1rem;'>
                    <span style='background: #ECFDF3; color: #166534; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.9rem;'>
                        ✓ Resolved
                    </span>
                </div>
                """, unsafe_allow_html=True
            )
        else:
            st.markdown(
                """
                <div style='display: flex; align-items: center; margin-bottom: 1rem;'>
                    <span style='background: #FFF7D6; color: #92400E; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.9rem;'>
                        ⚠️ Unable to fully resolve
                    </span>
                </div>
                """, unsafe_allow_html=True
            )

        st.markdown(final_response)

        # Extract and format ticket information if present
        import re
        ticket_match = re.search(r'(TKT-\d+)', final_response)
        if ticket_match:
            ticket_id = ticket_match.group(1)
            st.markdown(
                f"""
                <div class="ticket-box" style="background: #F5EEFF; border: 1px solid #DCC7F5; padding: 1rem; border-radius: 8px; margin-top: 1rem;">
                    <h4 style="margin: 0 0 8px 0; color: #6B21A8;">🎫 Support Ticket Created</h4>
                    <p style="margin: 0; font-size: 0.95rem;"><strong>Ticket ID:</strong> <span style="color: #6B21A8;">{ticket_id}</span></p>
                    <p style="margin: 4px 0 8px 0; font-size: 0.95rem;"><strong>Status:</strong> <span style='background: #EDE9FE; color: #6B21A8; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 600;'>OPEN</span></p>
                    <p style="margin: 0; color: #6B21A8; opacity: 0.8; font-size: 0.9rem;">Our support team will review your request shortly.</p>
                </div>
                """, unsafe_allow_html=True
            )