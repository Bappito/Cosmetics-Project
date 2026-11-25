"""Personal what-if simulator: each person's scenarios of planned orders, with the shortages they cause.

Scenarios are keyed by the name typed at sign-in. That keeps them apart, but it is not a secure
account: anyone who knows the password can type another name.
"""
from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from cosmetics_erp.services.bom import PARENT_TYPES
from cosmetics_erp.services.mrp import WEEKS
from cosmetics_erp.services.scenario import scenario_shortages
from cosmetics_erp.ui.context import PageContext

WEIGHT_TYPES = ("RAW", "BULK")


def _open_pos(ctx: PageContext) -> pd.DataFrame:
    po = pd.read_sql(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled')",
        ctx.conn,
    )
    po["qty_base"] = [
        float(w if t in WEIGHT_TYPES else u or 0.0)
        for w, u, t in zip(po["order_weight_grams"], po["order_qty_units"], po["item_type"])
    ]
    po["week"] = po["eta_date"].map(ctx.eta_to_week)
    return po


def _load(conn, scenario_id: int) -> dict:
    row = conn.execute("SELECT scenario_id, owner, name, shared, lines FROM Scenarios WHERE scenario_id = ?", (scenario_id,)).fetchone()
    return {"id": row[0], "owner": row[1], "name": row[2], "shared": bool(row[3]), "lines": json.loads(row[4] or "[]")}


def _results(ctx: PageContext, lines: list[dict]) -> pd.DataFrame:
    catalog = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams, min_order_qty, main_supplier, primary_warehouse FROM Catalog", ctx.conn)
    bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", ctx.conn)
    return scenario_shortages(catalog, bom, _open_pos(ctx), lines)


def render(ctx: PageContext) -> None:
    L = ctx.L
    conn = ctx.conn
    owner = st.session_state.get("user_name", "")
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{L("סימולטור אישי", "My simulator")}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "תרחיש פרטי שלך: הזמנות מתוכננות לפי שבוע, מול המלאי וההזמנות הפתוחות. רק אתה רואה אותו עד שתשתף.",
        "Your private scenario: planned orders by week, against stock and open orders. Only you see it until you share it.",
    ))
    products = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn)
    product_skus = products[products["item_type"].isin(PARENT_TYPES)]["sku"].tolist()

    mine = conn.execute("SELECT scenario_id, name FROM Scenarios WHERE owner = ? ORDER BY scenario_id", (owner,)).fetchall()
    with st.form("new_scenario", clear_on_submit=True):
        new_name = st.text_input(L("שם תרחיש חדש", "New scenario name"))
        if st.form_submit_button(L("צור תרחיש", "Create scenario")) and new_name.strip():
            conn.execute("INSERT INTO Scenarios (owner, name) VALUES (?, ?)", (owner, new_name.strip()[:120]))
            conn.commit()
            st.rerun()

    if not mine:
        st.info(L("אין לך עדיין תרחישים. צור אחד למעלה.", "You have no scenarios yet. Create one above."))
    else:
        labels = {sid: name for sid, name in mine}
        chosen = st.selectbox(L("התרחיש שלי", "My scenario"), list(labels), format_func=lambda i: labels[i], key="scenario_pick")
        scenario = _load(conn, chosen)
        lines_df = pd.DataFrame(scenario["lines"] or [{"sku": "", "week": 1, "qty": 0.0}], columns=["sku", "week", "qty"])
        edited = st.data_editor(
            lines_df,
            num_rows="dynamic",
            hide_index=True,
            width="stretch",
            key=f"scenario_lines_{chosen}",
            column_config={
                "sku": st.column_config.SelectboxColumn(L("מוצר", "Product"), options=product_skus, required=True),
                "week": st.column_config.SelectboxColumn(L("שבוע", "Week"), options=list(range(1, len(WEEKS) + 1)), required=True),
                "qty": st.column_config.NumberColumn(L("כמות (יחידות)", "Quantity (units)"), min_value=0.0),
            },
        )
        clean = [
            {"sku": str(r.sku), "week": int(r.week), "qty": float(r.qty)}
            for r in edited.itertuples()
            if str(r.sku or "").strip() and pd.notna(r.week) and pd.notna(r.qty) and float(r.qty) > 0
        ]
        b1, b2, b3 = st.columns(3)
        if b1.button(L("שמור תרחיש", "Save scenario"), type="primary"):
            conn.execute("UPDATE Scenarios SET lines = ? WHERE scenario_id = ?", (json.dumps(clean), chosen))
            conn.commit()
            st.session_state["flash"] = L("התרחיש נשמר.", "Scenario saved.")
            st.rerun()
        shared = b2.toggle(L("שתף לצפייה", "Share for viewing"), value=scenario["shared"], key=f"share_{chosen}")
        if shared != scenario["shared"]:
            conn.execute("UPDATE Scenarios SET shared = ? WHERE scenario_id = ?", (int(shared), chosen))
            conn.commit()
            st.rerun()
        if b3.button(L("מחק תרחיש", "Delete scenario")):
            conn.execute("DELETE FROM Scenarios WHERE scenario_id = ?", (chosen,))
            conn.commit()
            st.rerun()
        st.subheader(L("מחסור והזמנות מוצעות", "Shortages and suggested orders"))
        result = _results(ctx, clean)
        if result.empty:
            st.success(L("התרחיש לא יוצר מחסור.", "This scenario causes no shortages."))
        else:
            st.dataframe(result, hide_index=True, width="stretch")

    others = conn.execute(
        "SELECT scenario_id, owner, name FROM Scenarios WHERE shared = 1 AND owner <> ? ORDER BY owner, name", (owner,)
    ).fetchall()
    if others:
        st.divider()
        st.subheader(L("תרחישים ששותפו איתי", "Scenarios shared with you"))
        labels = {sid: f"{who}: {name}" for sid, who, name in others}
        pick = st.selectbox(L("בחר תרחיש לצפייה", "Pick a scenario to view"), list(labels), format_func=lambda i: labels[i], key="scenario_shared_pick")
        view = _load(conn, pick)
        st.dataframe(pd.DataFrame(view["lines"], columns=["sku", "week", "qty"]), hide_index=True, width="stretch")
        result = _results(ctx, view["lines"])
        if not result.empty:
            st.dataframe(result, hide_index=True, width="stretch")
