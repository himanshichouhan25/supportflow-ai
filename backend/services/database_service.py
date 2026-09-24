# ---------------------------------------------------------------------------
# Product Catalog
# ---------------------------------------------------------------------------

def render_product_card(product) -> bool:
    """
    Render one product card.

    Returns True when the customer clicks View Product.
    """
    with st.container(border=True):
        st.markdown(f"### 🛍️ {product.name}")

        if product.category:
            st.caption(product.category)

        st.markdown(f"## ₹{product.price:,.2f}")

        return st.button(
            "View Product",
            key=f"view_product_{product.product_id}",
            use_container_width=True,
        )