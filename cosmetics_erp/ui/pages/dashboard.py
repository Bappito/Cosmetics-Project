from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from cosmetics_erp.services.capacity import packable_units
from cosmetics_erp.services.costing import product_margins
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
                L("מק\"ט", "SKU"): capacity["sku"],
                L("פריט", "Item"): capacity["name"],
                L("ניתן לארוז (יח')", "Can pack (units)"): capacity["packable_units"],
                L("הרכיב המגביל", "Limiting component"): capacity["limiting_component"],
            }),
            hide_index=True,
        )

    st.subheader(L("רווח משוער מכל מוצר סופי", "Estimated profit per finished product"))
    margins = product_margins(cat, bom)
    if margins.empty:
        st.caption(L("אין מוצרים סופיים בקטלוג.", "No finished products in the catalog."))
    else:
        margins["label"] = margins["sku"] + " - " + margins["name"].fillna("")
        cost_label = L("עלות ליחידה", "Cost per unit")
        profit_label = L("רווח ליחידה", "Profit per unit")
        chart_rows = []
        for row in margins.itertuples():
            chart_rows.append({"product": row.label, "part": cost_label, "value": max(row.cost, 0.0)})
            chart_rows.append({"product": row.label, "part": profit_label, "value": max(row.margin, 0.0)})
        chart_df = pd.DataFrame(chart_rows)
        fig = px.bar(
            chart_df,
            x="value",
            y="product",
            color="part",
            orientation="h",
            barmode="stack",
            color_discrete_map={cost_label: "#cbd5e1", profit_label: "#0284c7"},
        )
        fig.update_layout(
            height=max(180, 90 * len(margins)),
            margin=dict(l=190, r=10, t=10, b=10),
            xaxis_title=L("₪ ליחידה (מחיר המכירה)", "₪ per unit (selling price)"),
            yaxis_title=None,
            legend_title=None,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig)

        profit_view = pd.DataFrame({
            L("מק\"ט", "SKU"): margins["sku"],
            L("פריט", "Item"): margins["name"].fillna("?"),
            L("מחיר מכירה", "Price"): margins["price"].map(lambda v: f"₪{v:,.2f}"),
            L("עלות", "Cost"): margins["cost"].map(lambda v: f"₪{v:,.2f}"),
            L("רווח ליחידה", "Profit / unit"): margins["margin"].map(lambda v: f"₪{v:,.2f}"),
            L("רווח %", "Margin %"): margins["margin_pct"].map(lambda v: "—" if pd.isna(v) else f"{v:,.1f}%"),
            L("מלאי (יח')", "Stock (units)"): margins["stock_units"].map(lambda v: f"{v:,.0f}"),
            L("רווח צפוי מהמלאי", "Profit on stock"): margins["stock_margin"].map(lambda v: f"₪{v:,.0f}"),
        })
        st.dataframe(profit_view, hide_index=True)
        st.caption(L(
            "העלות מחושבת לפי ה-BOM ומחירי הקטלוג (חומרי גלם ואריזות). מחיר המכירה הוא item_price של המוצר הסופי.",
            "Cost is calculated from the BOM and catalog prices (raw materials and packaging). Selling price is the finished product's item_price.",
        ))

    st.subheader(L("תפוגות קרובות", "Nearest expiry dates"))
    nearest = batches[batches["exp"].notna()].sort_values("exp").head(8)
    if nearest.empty:
        st.caption(L("אין אצוות עם תאריך תפוגה.", "No batches with an expiry date."))
    else:
        is_w = nearest["item_type"].isin(["RAW", "BULK"])
        nearest_view = pd.DataFrame({
            L("מק\"ט", "SKU"): nearest["sku"],
            L("פריט", "Item"): nearest["name"].fillna("?"),
            L("אצווה", "Batch"): nearest["batch_no"],
            L("כמות", "Qty"): [
                fmt_val(float(w if weighted else q), weighted)
                for w, q, weighted in zip(nearest["weight_grams"], nearest["qty_units"], is_w)
            ],
            L("תפוגה", "Expiry"): nearest["expiry_date"].map(lambda v: format_date(v, is_he=is_he)),
        })
        st.dataframe(nearest_view, hide_index=True)

    st.subheader(L("הזמנות רכש פתוחות לפי ETA", "Open purchase orders by ETA"))
    if pos.empty:
        st.caption(L("אין הזמנות רכש פתוחות.", "No open purchase orders."))
    else:
        po_view = pd.DataFrame({
            L("הזמנה", "PO"): pos["po_number"],
            L("מק\"ט", "SKU"): pos["sku"],
            L("פריט", "Item"): pos["name"].fillna("?"),
            L("ספק", "Supplier"): pos["supplier"],
            "ETA": pos["eta_date"].map(lambda v: format_date(v, is_he=is_he)),
            L("סטטוס", "Status"): pos["status"],
        })
        st.dataframe(po_view, hide_index=True)
