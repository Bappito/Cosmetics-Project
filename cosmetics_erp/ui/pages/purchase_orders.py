from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    CLOSED_PO_STATUSES = ctx.CLOSED_PO_STATUSES
    L = ctx.L
    UI = ctx.UI
    add_batch = ctx.add_batch
    conn = ctx.conn
    eta_week_label = ctx.eta_week_label
    fmt_val = ctx.fmt_val
    gen_batch_no = ctx.gen_batch_no
    log_move = ctx.log_move
    push_backup = ctx.push_backup
    render_undo_button = ctx.render_undo_button
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    cat_meta = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn).set_index("sku")

    st.subheader(L("הזמנות רכש פתוחות ושבוע ההגעה שלהן בסימולטורים", "Open POs & Arrival Week in Simulators"))
    open_df = df_po[~df_po["status"].isin(list(CLOSED_PO_STATUSES))]
    if open_df.empty:
        st.caption(L("אין הזמנות רכש פתוחות.", "No open purchase orders."))
    else:
        view_rows = []
        for r in open_df.itertuples():
            tp = cat_meta.loc[r.sku]["item_type"] if r.sku in cat_meta.index else "RAW"
            nm = cat_meta.loc[r.sku]["name"] if r.sku in cat_meta.index else "?"
            is_w_po = tp in ("RAW", "BULK")
            amt_plain = fmt_val(float(r.order_weight_grams if is_w_po else r.order_qty_units), is_w_po)
            view_rows.append({
                L("הזמנה", "PO"): r.po_number,
                L("מק\"ט", "SKU"): r.sku,
                L("פריט", "Item"): nm,
                L("ספק", "Supplier"): r.supplier,
                L("כמות", "Qty"): amt_plain,
                "ETA": r.eta_date,
                L("נכנס למאזן בשבוע", "Counted in week"): eta_week_label(r.eta_date),
                L("סטטוס", "Status"): r.status,
            })
        st.dataframe(pd.DataFrame(view_rows), use_container_width=True, hide_index=True)

    st.subheader(L("עריכת הזמנות רכש", "Edit purchase orders"))
    ed_po = st.data_editor(
        df_po, use_container_width=True, hide_index=True, num_rows="dynamic", key="po_editor",
        column_config={
            "status": st.column_config.SelectboxColumn("status", options=["In Transit", "Confirmed", "Received", "Cancelled"]),
        }
    )

    kept_pos = set(str(x).strip() for x in ed_po["po_number"].dropna() if str(x).strip())
    removed_pos = sorted(set(str(x) for x in df_po["po_number"].dropna()) - kept_pos)
    confirm_po_del = True
    if removed_pos:
        st.warning(f"{len(removed_pos)} הזמנות יימחקו אם תשמור: {', '.join(removed_pos)}.")
        confirm_po_del = st.checkbox("אני מאשר/ת את מחיקת ההזמנות האלה", key="po_del_confirm")

    pb1, pb2 = st.columns(2)
    with pb1:
        save_po = st.button(":material/save: שמור הזמנות רכש", disabled=not confirm_po_del)
    with pb2:
        render_undo_button("stock", "undo_po")

    if save_po:
        push_backup("stock", L("שמירת הזמנות רכש", "PO save"))
        conn.execute("DELETE FROM PurchaseOrders")
        for _, r in ed_po.iterrows():
            if pd.notna(r["po_number"]) and pd.notna(r["sku"]):
                conn.execute("""
                    INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (str(r["po_number"]), str(r["sku"]), str(r["supplier"] or ""), float(r["order_qty_units"] or 0),
                      float(r["order_weight_grams"] or 0), float(r["unit_price"] or 0), str(r["order_date"] or ""),
                      str(r["eta_date"] or ""), str(r["target_wh"] or "WH_RAW"), str(r["status"] or "In Transit")))
        conn.commit()
        st.session_state["flash"] = "נשמר!"
        st.rerun()

    st.divider()
    st.subheader(L("קבלת הזמנה למחסן (יוצר אצווה + תפוגה)", "Receive PO into warehouse (creates batch + expiry)"))
    if not open_df.empty:
        po_opts = [f"{r.po_number} | {r.sku}" for r in open_df.itertuples()]
        sel_po = st.selectbox(L("בחר הזמנה לקבלה:", "Select PO to receive:"), po_opts, key="rcv_po_sel")
        sel_po_num = sel_po.split(" | ")[0]
        po_row = open_df[open_df["po_number"] == sel_po_num].iloc[0]
        rcv_sku = str(po_row["sku"])
        rcv_tp = cat_meta.loc[rcv_sku]["item_type"] if rcv_sku in cat_meta.index else None
        if rcv_tp is not None:
            rcv_is_w = rcv_tp in ("RAW", "BULK")
            rcv_amt = float(po_row["order_weight_grams"] if rcv_is_w else po_row["order_qty_units"])
            rc1, rc2, rc3 = st.columns([2, 1.5, 1.5])
            with rc1:
                rcv_batch = st.text_input(L("מספר אצווה (Batch #) מהספק:", "Supplier Batch #:"),
                                          value=f"LOT-{rcv_sku}-{sel_po_num}", key=f"rcv_bno_{sel_po_num}")
            with rc2:
                rcv_exp = st.date_input(L("תאריך תפוגה:", "Expiry date:"),
                                        value=date.today() + timedelta(days=365), key=f"rcv_exp_{sel_po_num}")
            with rc3:
                rcv_no_exp = st.checkbox(L("ללא תפוגה", "No expiry"), value=(rcv_tp == "PKG"), key=f"rcv_noexp_{sel_po_num}")
            if st.button(L(":material/download_done: קבל למחסן", ":material/download_done: Receive into warehouse"), key="rcv_btn"):
                push_backup("stock", f"{L('קבלת', 'Receive')} {sel_po_num}")
                bno = (rcv_batch or "").strip() or gen_batch_no(rcv_sku)
                exp_s = "" if rcv_no_exp else rcv_exp.strftime("%Y-%m-%d")
                add_batch(rcv_sku, bno, rcv_amt, rcv_is_w, exp_s, "PO")
                log_move(rcv_sku, "WH_VENDOR", str(po_row["target_wh"] or "WH_RAW"), rcv_amt, rcv_is_w, f"{sel_po_num} / {bno}")
                now_d = datetime.now().strftime("%Y-%m-%d")
                if rcv_is_w:
                    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                                 (rcv_amt, f"+{rcv_amt/1000:.2f} ק\"ג מקבלת {sel_po_num}", f"{now_d} (+{rcv_amt/1000:.2f} ק\"ג)", rcv_sku))
                else:
                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                                 (rcv_amt, f"+{rcv_amt:.0f} יח' מקבלת {sel_po_num}", f"{now_d} (+{rcv_amt:.0f} יח')", rcv_sku))
                conn.execute("UPDATE PurchaseOrders SET status='Received' WHERE po_number=?", (sel_po_num,))
                conn.commit()
                st.session_state["flash"] = f"הזמנה {sel_po_num} התקבלה: אצווה {bno}, תפוגה {exp_s or 'ללא'}."
                st.rerun()
