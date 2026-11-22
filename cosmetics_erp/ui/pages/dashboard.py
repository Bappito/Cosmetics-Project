from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from cosmetics_erp.services.capacity import packable_units
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_date

EXPIRY_WARNING_DAYS = 30


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    fmt_val = ctx.fmt_val
    is_he = ctx.is_he
    parse_date = ctx.parse_date

    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_dash"]}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "סקירה כללית של המלאי, תאריכי התפוגה וההזמנות הפתוחות.",
        "Overview of stock levels, expiry dates, and open purchase orders.",
    ))

    cat = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams, item_price FROM Catalog", conn)
    bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", conn)
    batches = pd.read_sql(
        "SELECT b.sku, c.name AS name, c.item_type AS item_type, b.batch_no, b.qty_units, b.weight_grams, b.expiry_date "
        "FROM Batches b LEFT JOIN Catalog c ON b.sku = c.sku WHERE b.status = 'Active'",
        conn,
    )
    pos = pd.read_sql(
        "SELECT po.po_number, po.sku, c.name AS name, po.supplier, po.eta_date, po.status "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled') ORDER BY po.eta_date",
        conn,
    )

    # Stock totals by warehouse.
    raw_g = cat.loc[cat["item_type"] == "RAW", "weight_grams"].sum()
    bulk_g = cat.loc[cat["item_type"] == "BULK", "weight_grams"].sum()
    pkg_u = cat.loc[cat["item_type"] == "PKG", "qty_units"].sum()
    fg_u = cat.loc[cat["item_type"] == "FG", "qty_units"].sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric(L("חומר גלם (RAW)", "Raw Materials (RAW)"), fmt_val(raw_g, True))
    k2.metric(L("בלקים (BULK)", "Bulks (BULK)"), fmt_val(bulk_g, True))
    k3.metric(L("אריזות (PKG)", "Packaging (PKG)"), fmt_val(pkg_u, False))
    k4.metric(L("מוצר סופי (FG)", "Finished Goods (FG)"), fmt_val(fg_u, False))

    # Expiry and PO health.
    today = date.today()
    soon_limit = today + timedelta(days=EXPIRY_WARNING_DAYS)
    batches["exp"] = batches["expiry_date"].map(parse_date)
    expired = batches[batches["exp"].notna() & (batches["exp"] < today)]
    expiring = batches[batches["exp"].notna() & (batches["exp"] >= today) & (batches["exp"] <= soon_limit)]

    s1, s2, s3 = st.columns(3)
    s1.metric(L("הזמנות רכש פתוחות", "Open purchase orders"), len(pos))
    s2.metric(L(f"אצוות שפגות ב-{EXPIRY_WARNING_DAYS} ימים", f"Batches expiring in {EXPIRY_WARNING_DAYS} days"), len(expiring))
    s3.metric(L("אצוות שפג תוקפן", "Expired active batches"), len(expired))

    st.subheader(L("כמה יחידות ניתן לארוז עכשיו", "Units that can be packed now"))
    capacity = packable_units(cat, bom)
    if capacity.empty:
        st.caption(L("אין מוצרים סופיים בקטלוג.", "No finished products in the catalog."))
    else:
        short_products = capacity[capacity["packable_units"] == 0]
        if not short_products.empty:
            st.warning(L(
                f"אי אפשר לארוז {len(short_products)} מוצרים כרגע בגלל חוסר ברכיב.",
                f"{len(short_products)} products cannot be packed right now because a component is short.",
            ))
        st.dataframe(
            pd.DataFrame({
                L("ניתן לארוז (יח')", "Can pack (units)"): capacity["packable_units"],
                L("הרכיב המגביל", "Limiting component"): capacity["limiting_component"],
                L("פריט", "Item"): capacity["name"],
                L("מק\"ט", "SKU"): capacity["sku"],
            }),
            hide_index=True,
        )

    st.subheader(L("תפוגות קרובות", "Nearest expiry dates"))
    nearest = batches[batches["exp"].notna()].sort_values("exp").head(8)
    if nearest.empty:
        st.caption(L("אין אצוות עם תאריך תפוגה.", "No batches with an expiry date."))
    else:
        is_w = nearest["item_type"].isin(["RAW", "BULK"])
        nearest_view = pd.DataFrame({
            L("אצווה", "Batch"): nearest["batch_no"],
            L("כמות", "Qty"): [
                fmt_val(float(w if weighted else q), weighted)
                for w, q, weighted in zip(nearest["weight_grams"], nearest["qty_units"], is_w)
            ],
            L("תפוגה", "Expiry"): nearest["expiry_date"].map(lambda v: format_date(v, is_he=is_he)),
            L("פריט", "Item"): nearest["name"].fillna("?"),
            L("מק\"ט", "SKU"): nearest["sku"],
        })
        st.dataframe(nearest_view, hide_index=True)

    st.subheader(L("הזמנות רכש פתוחות לפי ETA", "Open purchase orders by ETA"))
    if pos.empty:
        st.caption(L("אין הזמנות רכש פתוחות.", "No open purchase orders."))
    else:
        po_view = pd.DataFrame({
            L("הזמנה", "PO"): pos["po_number"],
            L("ספק", "Supplier"): pos["supplier"],
            "ETA": pos["eta_date"].map(lambda v: format_date(v, is_he=is_he)),
            L("סטטוס", "Status"): pos["status"],
            L("פריט", "Item"): pos["name"].fillna("?"),
            L("מק\"ט", "SKU"): pos["sku"],
        })
        st.dataframe(po_view, hide_index=True)
