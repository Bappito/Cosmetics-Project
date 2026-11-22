from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import streamlit as st

from cosmetics_erp.services.mrp import monthly_summary, mrp_suggestions, week_starts, weekly_excel_bytes
from cosmetics_erp.services.planning import current_plan_start
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import sku_first

WEIGHT_TYPES = ("RAW", "BULK")


def render(ctx: PageContext) -> None:
    L = ctx.L
    is_he = ctx.is_he
    UI = ctx.UI
    conn = ctx.conn
    fmt_val = ctx.fmt_val

    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_mrp"]}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "מחשב מה צריך לקנות לפי תוכנית 8 השבועות, המלאי הנוכחי, ההזמנות הפתוחות וה-BOM. ההצעות מעוגלות לכמות ההזמנה המינימלית (MOQ).",
        "Works out what to buy from the 8-week plan, current stock, open purchase orders, and the BOM. Suggestions are rounded up to the minimum order quantity (MOQ).",
    ))

    catalog = pd.read_sql(
        "SELECT sku, name, item_type, qty_units, weight_grams, min_order_qty, main_supplier, primary_warehouse FROM Catalog",
        conn,
    )
    bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", conn)
    schedule = pd.read_sql(
        "SELECT parent_sku, W1, W2, W3, W4, W5, W6, W7, W8 FROM WeeklySchedule", conn
    )
    po_rows = pd.read_sql(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled')",
        conn,
    )
    po_rows["qty_base"] = [
        float(w if t in WEIGHT_TYPES else u or 0.0)
        for w, u, t in zip(po_rows["order_weight_grams"], po_rows["order_qty_units"], po_rows["item_type"])
    ]
    po_rows["week"] = po_rows["eta_date"].map(ctx.eta_to_week)

    suggestions = mrp_suggestions(catalog, bom, schedule, po_rows)
    if suggestions.empty:
        st.success(L("אין צורך ברכש נוסף לתוכנית הנוכחית.", "No purchases needed for the current plan."))
        return

    plan_start = current_plan_start()
    summary = monthly_summary(suggestions, plan_start).copy()
    summary["is_weight"] = summary["item_type"].isin(WEIGHT_TYPES)
    table = pd.DataFrame({
        L("מק\"ט", "SKU"): summary["sku"],
        L("פריט", "Item"): summary["name"],
        L("חודש", "Month"): summary["month"],
        L("חסר בחודש", "Short in month"): [fmt_val(v, w) for v, w in zip(summary["shortfall_base"], summary["is_weight"])],
        L("להזמין בחודש", "To order in month"): [fmt_val(v, w) for v, w in zip(summary["order_base"], summary["is_weight"])],
        L("ספק", "Supplier"): summary["supplier"],
    })
    st.caption(L(
        "סיכום לפי חודש. להורדה לאקסל יש פירוט שבועי.",
        "Summary by month. The Excel download has the weekly detail.",
    ))
    st.dataframe(table, column_order=sku_first(table.columns, is_he), width="stretch", hide_index=True)
    headers = [
        L("מק\"ט", "SKU"), L("פריט", "Item"), L("סוג", "Type"), L("שבוע", "Week"),
        L("תחילת שבוע", "Week start"), L("סוף שבוע", "Week end"), L("חודש", "Month"),
        L("חסר", "Short"), L("להזמין", "To order"), L("יחידה", "Unit"), L("ספק", "Supplier"),
    ]
    st.download_button(
        L(":material/download: הורד לאקסל (שבועי)", ":material/download: Download Excel (weekly)"),
        data=weekly_excel_bytes(suggestions, plan_start, headers),
        file_name=f"mrp-weekly-{date.today():%Y%m%d}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="mrp_download",
    )

    st.caption(L(
        "ההזמנות נוצרות כטיוטה עם תאריך הגעה בתחילת השבוע הנדרש. טיוטות נחשבות כהזמנות פתוחות, ולכן לא ייווצרו שוב בהרצה הבאה.",
        "Drafts are created with an arrival date at the start of the needed week. Drafts count as open orders, so running this again will not duplicate them.",
    ))
    confirm = st.checkbox(L("בדקתי את ההצעות ואני מאשר/ת ליצור הזמנות טיוטה.", "I reviewed the suggestions and confirm creating draft orders."), key="mrp_confirm")
    if st.button(L(":material/post_add: צור הזמנות טיוטה", ":material/post_add: Create draft POs"), key="mrp_create", type="primary", disabled=not confirm):
        ctx.push_backup("stock", L("תכנון רכש (MRP)", "MRP draft orders"))
        plan_start = current_plan_start()
        stamp = datetime.now().strftime("%y%m%d")
        cat_idx = catalog.set_index("sku")
        # Drafts follow the monthly summary: one order per product per month, arriving at the
        # start of the first week of that month.
        first_week = week_starts(plan_start).groupby("month")["week_start"].min()
        for n, row in enumerate(summary.itertuples(), start=1):
            is_w = row.item_type in WEIGHT_TYPES
            eta = first_week[row.month].strftime("%Y-%m-%d")
            target_wh = cat_idx.loc[row.sku, "primary_warehouse"] or "WH_RAW"
            conn.execute(
                "INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    f"MRP-{stamp}-{n:03d}",
                    row.sku,
                    row.supplier,
                    0.0 if is_w else float(row.order_base),
                    float(row.order_base) if is_w else 0.0,
                    0.0,
                    date.today().strftime("%Y-%m-%d"),
                    eta,
                    target_wh,
                    "Draft",
                ),
            )
        conn.commit()
        st.session_state["flash"] = L(f"נוצרו {len(summary)} הזמנות טיוטה (לפי חודש).", f"Created {len(summary)} draft orders (by month).")
        st.rerun()
