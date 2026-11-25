"""PRR (project readiness): each component's weekly stock, coloured by the readiness rule.

A product's tree is treated as its project. Green: stock on hand covers the need. Yellow: short
on stock alone, but an open purchase order arrives in time. Red: still short even with every arrival.
"""
from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from cosmetics_erp.services.where_used import COVERED, IDLE, READY, SHORT, WEEKS, readiness
from cosmetics_erp.ui.context import PageContext

CLASS = {READY: "prr-green", COVERED: "prr-yellow", SHORT: "prr-red", IDLE: "prr-none"}


def _bom_rows(conn) -> list[dict]:
    df = pd.read_sql("""
        SELECT b.component_sku, c.name AS comp_name, c.item_type AS comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               COALESCE(s.W1,0) AS W1, COALESCE(s.W2,0) AS W2, COALESCE(s.W3,0) AS W3, COALESCE(s.W4,0) AS W4,
               COALESCE(s.W5,0) AS W5, COALESCE(s.W6,0) AS W6, COALESCE(s.W7,0) AS W7, COALESCE(s.W8,0) AS W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        LEFT JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        ORDER BY b.component_sku, b.parent_sku
    """, conn)
    return df.to_dict("records")


def render(ctx: PageContext) -> None:
    L = ctx.L
    conn = ctx.conn
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{L("PRR: מוכנות פרויקט", "PRR: project readiness")}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "ירוק = מלאי קיים מספיק. צהוב = חסר עד הגעת הזמנת רכש. אדום = חסר גם עם כל ההגעות.",
        "Green = stock on hand is enough. Yellow = short until a purchase order arrives. Red = short even with every arrival.",
    ))
    rows = _bom_rows(conn)
    if not rows:
        st.info(L("אין עצי מוצר בקטלוג.", "No product trees in the catalog."))
        return
    projects = sorted({r["parent_sku"] for r in rows})
    names = {r["parent_sku"]: r["parent_name"] for r in rows}
    project = st.selectbox(
        L("פרויקט (עץ מוצר)", "Project (product tree)"),
        projects,
        format_func=lambda s: f"{s} - {names.get(s, '')}",
        key="prr_project",
    )
    result = readiness(rows, ctx.get_incoming_map())
    counts = {READY: 0, COVERED: 0, SHORT: 0}
    body = []
    for idx, r in enumerate(rows):
        if r["parent_sku"] != project:
            continue
        is_w = r["comp_type"] in ("RAW", "BULK")
        cells = []
        for cell in result["cells"][idx]:
            if cell["status"] in counts:
                counts[cell["status"]] += 1
            value = "—" if cell["status"] == IDLE else ctx.fmt_val(cell["after"], is_w)
            title = escape(f"{ctx.fmt_val(cell['stock_only'], is_w)} / {ctx.fmt_val(cell['used'], is_w)}")
            cells.append(f"<td class='{CLASS[cell['status']]}' title='{title}'>{value}</td>")
        body.append(
            f"<tr><td class='parent-col'><span class='chip'>{escape(r['component_sku'])}</span> {escape(str(r['comp_name']))}</td>"
            f"<td>{ctx.fmt_val(float(r['avail_grams'] if is_w else r['avail_units']), is_w)}</td>{''.join(cells)}</tr>"
        )
    c1, c2, c3 = st.columns(3)
    c1.metric(L("ירוק", "Green"), counts[READY])
    c2.metric(L("צהוב", "Yellow"), counts[COVERED])
    c3.metric(L("אדום", "Red"), counts[SHORT])
    head = "".join(f"<th>{escape(w)}</th>" for w in WEEKS)
    st.markdown(
        "<style>.prr-green{background:#dcfce7;color:#15803d;font-weight:700}"
        ".prr-yellow{background:#fef9c3;color:#a16207;font-weight:700}"
        ".prr-red{background:#fee2e2;color:#b91c1c;font-weight:700}</style>"
        f"<div class='table-responsive'><table class='matrix-table'><thead><tr><th>{L('מק״ט ופריט', 'SKU & item')}</th>"
        f"<th>{L('מלאי נוכחי', 'Current stock')}</th>{head}</tr></thead><tbody>{''.join(body)}</tbody></table></div>",
        unsafe_allow_html=True,
    )
