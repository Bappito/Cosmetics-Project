from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from cosmetics_erp.ui.change_review import summarize_editor_changes
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_date


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
    is_he = ctx.is_he
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    cat_meta = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn).set_index("sku")

    st.subheader(L("הזמנות רכש פתוחות ושבוע ההגעה שלהן בסימולטורים", "Open POs & Arrival Week in Simulators"))
    open_df = df_po[~df_po["status"].isin(list(CLOSED_PO_STATUSES))]
    if open_df.empty:
        st.caption(L("אין הזמנות רכש פתוחות.", "No open purchase orders."))
    else:
        search_col, status_col = st.columns([2, 1])
        with search_col:
            po_search = st.text_input(
                L("חיפוש הזמנה, מק\"ט או ספק", "Search PO, SKU, or supplier"),
                key="po_open_search",
            ).strip()
        with status_col:
            all_statuses = L("כל הסטטוסים", "All statuses")
            po_status = st.selectbox(
                L("סינון לפי סטטוס", "Filter by status"),
                [all_statuses, *sorted(open_df["status"].dropna().unique())],
                key="po_open_status_filter",
            )
        filtered_open_df = open_df
        if po_status != all_statuses:
            filtered_open_df = filtered_open_df[filtered_open_df["status"] == po_status]
        if po_search:
            searchable = filtered_open_df[["po_number", "sku", "supplier", "status"]].fillna("").astype(str)
            matches = searchable.apply(
                lambda column: column.str.contains(po_search, case=False, regex=False)
            ).any(axis=1)
            filtered_open_df = filtered_open_df[matches]

        st.caption(L(
            f"מוצגות {len(filtered_open_df)} מתוך {len(open_df)} הזמנות פתוחות",
            f"Showing {len(filtered_open_df)} of {len(open_df)} open orders",
        ))
        if filtered_open_df.empty:
            st.info(L("לא נמצאו הזמנות התואמות לסינון.", "No orders match these filters."))
        else:
            view_rows = []
            for r in filtered_open_df.itertuples():
                tp = cat_meta.loc[r.sku]["item_type"] if r.sku in cat_meta.index else "RAW"
                nm = cat_meta.loc[r.sku]["name"] if r.sku in cat_meta.index else "?"
                is_w_po = tp in ("RAW", "BULK")
                amt_plain = fmt_val(float(r.order_weight_grams if is_w_po else r.order_qty_units), is_w_po)
                view_rows.append({
                    L("הזמנה", "PO"): r.po_number,
                    L("ספק", "Supplier"): r.supplier,
                    L("כמות", "Qty"): amt_plain,
                    "ETA": format_date(r.eta_date, is_he=is_he),
                    L("נכנס למאזן בשבוע", "Counted in week"): eta_week_label(r.eta_date),
                    L("סטטוס", "Status"): r.status,
                    L("פריט", "Item"): nm,
                    L("מק\"ט", "SKU"): r.sku,
                })
            st.dataframe(
                pd.DataFrame(view_rows),
                width="stretch",
                hide_index=True,
                column_config={
                    L("הזמנה", "PO"): st.column_config.TextColumn(L("הזמנה", "PO"), width="small"),
                    L("מק\"ט", "SKU"): st.column_config.TextColumn(L("מק\"ט", "SKU"), width="small"),
                    L("סטטוס", "Status"): st.column_config.TextColumn(L("סטטוס", "Status"), width="small"),
                },
            )

    st.subheader(L("עריכת הזמנות רכש", "Edit purchase orders"))
    po_review_key = "po_review_pending"
    po_review_version_key = "po_review_version"
    po_review_version = st.session_state.get(po_review_version_key, 0)
    po_confirm_key = f"po_review_confirmed_{po_review_version}"
    ed_po = st.data_editor(
        df_po,
        column_order=[c for c in df_po.columns if c != "sku"] + ["sku"],
        width="stretch",
        hide_index=True,
        num_rows="dynamic",
        key="po_editor",
        disabled=True if st.session_state.get(po_review_key, False) else ["po_id"],
        column_config={
            "status": st.column_config.SelectboxColumn(
                L("סטטוס", "Status"),
                options=["In Transit", "Confirmed", "Received", "Cancelled"],
            ),
        }
    )

    po_number_values = ed_po["po_number"].fillna("").astype(str).str.strip()
    sku_values = ed_po["sku"].fillna("").astype(str).str.strip()
    has_any_data = ed_po.drop(columns=["po_id"], errors="ignore").apply(
        lambda column: column.notna() & column.astype(str).str.strip().ne("")
    ).any(axis=1)
    duplicate_po_mask = po_number_values.ne("") & po_number_values.duplicated(keep=False)
    duplicate_pos = sorted(po_number_values[duplicate_po_mask].unique())
    invalid_quantities = pd.Series(False, index=ed_po.index)
    for quantity_column in ("order_qty_units", "order_weight_grams", "unit_price"):
        numeric_values = pd.to_numeric(ed_po[quantity_column], errors="coerce")
        invalid_quantities |= (ed_po[quantity_column].notna() & numeric_values.isna()) | (numeric_values < 0)
    validation_errors = []
    incomplete_rows = has_any_data & (po_number_values.eq("") | sku_values.eq(""))
    if incomplete_rows.any():
        validation_errors.append(L("לכל הזמנה נדרשים מספר PO ומק\"ט.", "Every order needs both a PO number and an SKU."))
    if duplicate_pos:
        validation_errors.append(L(
            f"מספרי PO כפולים: {', '.join(duplicate_pos)}.",
            f"Duplicate PO numbers: {', '.join(duplicate_pos)}.",
        ))
    unknown_skus = sorted(set(sku_values[has_any_data & sku_values.ne("")]) - set(cat_meta.index))
    if unknown_skus:
        validation_errors.append(L(
            f"מק\"טים שלא קיימים בקטלוג: {', '.join(unknown_skus)}.",
            f"SKUs not found in the catalog: {', '.join(unknown_skus)}.",
        ))
    if invalid_quantities.any():
        validation_errors.append(L("כמויות ומחירים חייבים להיות מספרים שאינם שליליים.", "Quantities and prices must be valid non-negative numbers."))
    allowed_statuses = {"In Transit", "Confirmed", "Received", "Cancelled"}
    invalid_statuses = sorted(set(ed_po.loc[has_any_data, "status"].dropna().astype(str)) - allowed_statuses)
    if invalid_statuses:
        validation_errors.append(L("נמצאו סטטוסים לא מוכרים בהזמנות.", "One or more orders have an unsupported status."))
    for error in validation_errors:
        st.error(error)

    po_compare_columns = [column for column in df_po.columns if column not in {"po_id", "po_number"}]
    po_changes = summarize_editor_changes(df_po, ed_po, "po_number", po_compare_columns)
    added_pos, removed_pos, changed_pos = po_changes
    po_has_changes = bool(any(po_changes))

    pb1, pb2 = st.columns(2)
    with pb1:
        review_po = st.button(
            L(":material/preview: בדוק שינויים בהזמנות", ":material/preview: Review PO changes"),
            key="po_review_button",
            disabled=bool(validation_errors) or not po_has_changes or st.session_state.get(po_review_key, False),
            type="primary",
        )
    with pb2:
        if not st.session_state.get(po_review_key, False):
            render_undo_button("stock", "undo_po")

    if review_po:
        st.session_state[po_review_key] = True
        st.session_state[po_review_version_key] = po_review_version + 1
        st.rerun()

    save_po = False
    if st.session_state.get(po_review_key, False):
        st.info(L(
            f"סקירת שינויים: {len(added_pos)} נוספו, {len(changed_pos)} עודכנו, {len(removed_pos)} יימחקו.",
            f"Change review: {len(added_pos)} added, {len(changed_pos)} changed, {len(removed_pos)} will be removed.",
        ))
        if removed_pos:
            st.warning(L(
                f"ההזמנות הבאות יימחקו: {', '.join(removed_pos)}",
                f"The following POs will be deleted: {', '.join(removed_pos)}",
            ))
        preview_pos = set(added_pos) | set(changed_pos)
        preview_rows = ed_po[po_number_values.isin(preview_pos)]
        if not preview_rows.empty:
            st.dataframe(preview_rows, width="stretch", hide_index=True)
        confirmed_po = st.checkbox(
            L("בדקתי את התצוגה המקדימה ואני מאשר/ת לשמור את השינויים.", "I reviewed the preview and confirm these changes."),
            key=po_confirm_key,
        )
        confirm_col, cancel_col = st.columns(2)
        with confirm_col:
            save_po = st.button(
                L(":material/save: אשר ושמור", ":material/save: Confirm and save"),
                key="po_confirm_button",
                disabled=not confirmed_po or bool(validation_errors),
                type="primary",
            )
        with cancel_col:
            cancel_po = st.button(L(":material/close: בטל", ":material/close: Cancel"), key="po_cancel_button")
        if cancel_po:
            st.session_state[po_review_key] = False
            st.rerun()

    if save_po:
        st.session_state[po_review_key] = False
        push_backup("stock", L("שמירת הזמנות רכש", "PO save"))
        # Update existing rows in place (keeps po_id stable), insert new rows, and delete only rows
        # the user removed from the editor. Previously every save recreated all rows with new IDs.
        existing_po_ids = {int(x) for x in df_po["po_id"]}
        kept_po_ids = set()
        for _, r in ed_po.iterrows():
            if not (pd.notna(r["po_number"]) and pd.notna(r["sku"])):
                continue
            values = (
                str(r["po_number"]).strip(),
                str(r["sku"]).strip(),
                "" if pd.isna(r["supplier"]) else str(r["supplier"]),
                0.0 if pd.isna(r["order_qty_units"]) else float(r["order_qty_units"]),
                0.0 if pd.isna(r["order_weight_grams"]) else float(r["order_weight_grams"]),
                0.0 if pd.isna(r["unit_price"]) else float(r["unit_price"]),
                "" if pd.isna(r["order_date"]) else str(r["order_date"]),
                "" if pd.isna(r["eta_date"]) else str(r["eta_date"]),
                "WH_RAW" if pd.isna(r["target_wh"]) or not str(r["target_wh"]).strip() else str(r["target_wh"]),
                "In Transit" if pd.isna(r["status"]) or not str(r["status"]).strip() else str(r["status"]),
            )
            row_id = None if pd.isna(r["po_id"]) else int(r["po_id"])
            if row_id in existing_po_ids:
                conn.execute("""
                    UPDATE PurchaseOrders SET po_number=?, sku=?, supplier=?, order_qty_units=?, order_weight_grams=?,
                        unit_price=?, order_date=?, eta_date=?, target_wh=?, status=?
                    WHERE po_id=?
                """, (*values, row_id))
                kept_po_ids.add(row_id)
            else:
                conn.execute("""
                    INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, values)
        for removed_id in existing_po_ids - kept_po_ids:
            conn.execute("DELETE FROM PurchaseOrders WHERE po_id=?", (removed_id,))
        conn.commit()
        st.session_state["flash"] = "נשמר!"
        st.rerun()

    st.divider()
    st.subheader(L("קבלת הזמנה למחסן (יוצר אצווה + תפוגה)", "Receive PO into warehouse (creates batch + expiry)"))
    if not open_df.empty:
        po_opts = [f"{r.po_number} | {r.sku}" for r in open_df.itertuples()]
        receive_review_key = "po_receipt_review_pending"
        receive_version_key = "po_receipt_review_version"
        receive_pending = st.session_state.get(receive_review_key, False)
        receive_version = st.session_state.get(receive_version_key, 0)
        receive_confirm_key = f"po_receipt_review_confirmed_{receive_version}"
        sel_po = st.selectbox(
            L("בחר הזמנה לקבלה:", "Select PO to receive:"),
            po_opts,
            key="rcv_po_sel",
            disabled=receive_pending,
        )
        sel_po_num = sel_po.split(" | ")[0]
        po_row = open_df[open_df["po_number"] == sel_po_num].iloc[0]
        rcv_sku = str(po_row["sku"])
        rcv_tp = cat_meta.loc[rcv_sku]["item_type"] if rcv_sku in cat_meta.index else None
        if rcv_tp is not None:
            rcv_is_w = rcv_tp in ("RAW", "BULK")
            raw_rcv_amount = pd.to_numeric(
                pd.Series([po_row["order_weight_grams"] if rcv_is_w else po_row["order_qty_units"]]),
                errors="coerce",
            ).iloc[0]
            rcv_amt = float(raw_rcv_amount) if pd.notna(raw_rcv_amount) else 0.0
            receive_is_valid = rcv_amt > 0
            with st.container(border=True):
                st.caption(L(
                    f"כמות להזמנה: {fmt_val(rcv_amt, rcv_is_w)} · יעד: {po_row['target_wh']}",
                    f"Order quantity: {fmt_val(rcv_amt, rcv_is_w)} · Destination: {po_row['target_wh']}",
                ))
                if not receive_is_valid:
                    st.error(L("כמות ההזמנה חייבת להיות גדולה מאפס.", "The order quantity must be greater than zero."))
                rc1, rc2, rc3 = st.columns([2, 1.5, 1.5])
                with rc1:
                    rcv_batch = st.text_input(
                        L("מספר אצווה (Batch #) מהספק:", "Supplier batch number"),
                        value=f"LOT-{rcv_sku}-{sel_po_num}",
                        key=f"rcv_bno_{sel_po_num}",
                        disabled=receive_pending,
                    )
                with rc2:
                    rcv_exp = st.date_input(
                        L("תאריך תפוגה:", "Expiry date"),
                        value=date.today() + timedelta(days=365),
                        key=f"rcv_exp_{sel_po_num}",
                        disabled=receive_pending,
                    )
                with rc3:
                    rcv_no_exp = st.checkbox(
                        L("ללא תפוגה", "No expiry"),
                        value=(rcv_tp == "PKG"),
                        key=f"rcv_noexp_{sel_po_num}",
                        disabled=receive_pending,
                    )
                review_receive = False
                if not receive_pending:
                    review_receive = st.button(
                        L(":material/preview: בדוק קבלה", ":material/preview: Review receipt"),
                        key="rcv_review_btn",
                        disabled=not receive_is_valid,
                        type="primary",
                    )
            if review_receive:
                st.session_state[receive_review_key] = True
                st.session_state[receive_version_key] = receive_version + 1
                st.rerun()

            receive_po = False
            if receive_pending:
                preview_batch = (rcv_batch or "").strip() or gen_batch_no(rcv_sku)
                preview_expiry = "" if rcv_no_exp else rcv_exp.strftime("%Y-%m-%d")
                st.info(L(
                    f"קבלה לסקירה: {sel_po_num} · {rcv_sku} · {fmt_val(rcv_amt, rcv_is_w)} · אצווה {preview_batch} · תפוגה {format_date(preview_expiry, is_he=is_he)}",
                    f"Receipt preview: {sel_po_num} · {rcv_sku} · {fmt_val(rcv_amt, rcv_is_w)} · batch {preview_batch} · expiry {format_date(preview_expiry, is_he=is_he)}",
                ))
                if rcv_exp < date.today() and not rcv_no_exp:
                    st.warning(L("תאריך התפוגה כבר עבר; האצווה תהיה חסומה לשימוש FEFO.", "This expiry date is in the past; FEFO will block the batch from use."))
                receipt_batch_taken = ctx.batch_exists(rcv_sku, preview_batch)
                if receipt_batch_taken:
                    st.error(L(
                        f"אצווה {preview_batch} כבר קיימת למק\"ט {rcv_sku}. ערוך/י את מספר האצווה לפני האישור.",
                        f"Batch {preview_batch} already exists for SKU {rcv_sku}. Edit the batch number before confirming.",
                    ))
                confirmed_receive = st.checkbox(
                    L("בדקתי את פרטי הקבלה ואני מאשר/ת לעדכן את המלאי.", "I reviewed the receipt and confirm the stock update."),
                    key=receive_confirm_key,
                )
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    receive_po = st.button(
                        L(":material/download_done: אשר קבלה", ":material/download_done: Confirm receipt"),
                        key="rcv_confirm_btn",
                        disabled=not confirmed_receive or not receive_is_valid or receipt_batch_taken,
                        type="primary",
                    )
                with cancel_col:
                    cancel_receive = st.button(L(":material/close: בטל", ":material/close: Cancel"), key="rcv_cancel_btn")
                if cancel_receive:
                    st.session_state[receive_review_key] = False
                    st.rerun()

            if receive_po:
                st.session_state[receive_review_key] = False
                push_backup("stock", f"{L('קבלת', 'Receive')} {sel_po_num}")
                bno = preview_batch
                exp_s = preview_expiry
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
