from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_date


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    add_batch = ctx.add_batch
    conn = ctx.conn
    fmt_val = ctx.fmt_val
    gen_batch_no = ctx.gen_batch_no
    parse_date = ctx.parse_date
    push_backup = ctx.push_backup
    render_undo_button = ctx.render_undo_button
    trace_chain = ctx.trace_chain
    w_factor = ctx.w_factor
    w_label = ctx.w_label
    is_he = ctx.is_he
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_batch"]}</h2></div>', unsafe_allow_html=True)

    df_b = pd.read_sql(
        "SELECT b.*, c.name, c.item_type FROM Batches b JOIN Catalog c ON b.sku = c.sku", conn
    )
    today_d = date.today()

    def days_left_fn(s):
        d_ = parse_date(s)
        return (d_ - today_d).days if d_ else None

    if not df_b.empty:
        df_b["days_left"] = df_b["expiry_date"].apply(days_left_fn)
    active_b = df_b[df_b["status"] == "Active"] if not df_b.empty else df_b
    n_active = len(active_b)
    n_expired = int((active_b["days_left"] < 0).sum()) if n_active else 0
    n_soon = int(((active_b["days_left"] >= 0) & (active_b["days_left"] <= 30)).sum()) if n_active else 0

    m1, m2, m3 = st.columns(3)
    m1.metric(L("אצוות פעילות", "Active batches"), n_active)
    m2.metric(L("פגות תוקף תוך 30 יום", "Expiring within 30 days"), n_soon)
    m3.metric(L("פגות תוקף (חסומות לשימוש)", "Expired (blocked)"), n_expired)

    t_b1, t_b2, t_b3 = st.tabs([
        L(":material/list_alt: מלאי לפי אצווה (FEFO)", ":material/list_alt: Stock by batch (FEFO)"),
        L(":material/add_box: כניסת מלאי ידנית עם אצווה", ":material/add_box: Manual receipt with batch"),
        L(":material/account_tree: עקיבות (Traceability)", ":material/account_tree: Traceability"),
    ])

    with t_b1:
        if not df_b.empty:
            fc1, fc2, fc3 = st.columns([1.5, 1.5, 2])
            with fc1:
                sku_opts = [L("הכל", "All")] + sorted(df_b["sku"].unique())
                sel_sku_b = st.selectbox(L("סנן לפי מק\"ט:", "Filter by SKU:"), sku_opts, key="batch_sku_filter")
            with fc2:
                show_depleted = st.checkbox(L("הצג גם אצוות שנוצלו", "Include depleted batches"), key="batch_show_dep")
            with fc3:
                batch_search = st.text_input(
                    L("חיפוש מק\"ט, פריט או אצווה", "Search SKU, item, or batch"),
                    key="batch_search",
                ).strip()
            view_b = df_b.copy()
            if sel_sku_b != L("הכל", "All"):
                view_b = view_b[view_b["sku"] == sel_sku_b]
            if not show_depleted:
                view_b = view_b[view_b["status"] == "Active"]
            if batch_search:
                searchable = view_b[["sku", "name", "batch_no"]].fillna("").astype(str)
                matches = searchable.apply(
                    lambda column: column.str.contains(batch_search, case=False, regex=False)
                ).any(axis=1)
                view_b = view_b[matches]
            st.caption(L(
                f"מוצגות {len(view_b)} אצוות",
                f"Showing {len(view_b)} batches",
            ))
            if not view_b.empty:
                view_b = view_b.assign(_noexp=view_b["expiry_date"].fillna("").eq("")).sort_values(["sku", "_noexp", "expiry_date", "batch_id"])
                out_rows = []
                for _, r in view_b.iterrows():
                    is_w_b = r["item_type"] in ("RAW", "BULK")
                    dl = r["days_left"]
                    out_rows.append({
                        L("מק\"ט", "SKU"): r["sku"],
                        L("פריט", "Item"): r["name"],
                        "Batch #": r["batch_no"],
                        L("יתרה", "Remaining"): fmt_val(float(r["weight_grams"] if is_w_b else r["qty_units"]), is_w_b),
                        L("תפוגה", "Expiry"): format_date(r["expiry_date"], is_he=is_he),
                        L("ימים לתפוגה", "Days left"): "-" if (dl is None or pd.isna(dl)) else str(int(dl)),
                        L("סטטוס", "Status"): L("פעילה", "Active") if r["status"] == "Active" else L("אזלה", "Depleted"),
                        L("מקור", "Source"): r["source"],
                        L("תאריך כניסה", "Received"): format_date(r["received_date"], is_he=is_he),
                    })
                st.dataframe(pd.DataFrame(out_rows), width="stretch", hide_index=True)
            else:
                st.info(L("לא נמצאו אצוות התואמות לסינון.", "No batches match these filters."))
        render_undo_button("stock", "undo_batches")

    with t_b2:
        cat_b = pd.read_sql("SELECT sku, name, item_type FROM Catalog ORDER BY sku", conn)
        manual_review_key = "manual_batch_review_pending"
        manual_version_key = "manual_batch_review_version"
        manual_pending = st.session_state.get(manual_review_key, False)
        manual_version = st.session_state.get(manual_version_key, 0)
        manual_confirm_key = f"manual_batch_review_confirmed_{manual_version}"
        sel_mb = st.selectbox(
            L("מק\"ט לכניסת מלאי:", "SKU to receive:"),
            cat_b["sku"] + " - " + cat_b["name"],
            key="mb_sku",
            disabled=manual_pending,
        )
        mb_sku = sel_mb.split(" - ")[0]
        mb_tp = cat_b[cat_b["sku"] == mb_sku].iloc[0]["item_type"]
        mb_is_w = mb_tp in ("RAW", "BULK")
        with st.container(border=True):
            st.caption(L(
                "הוספת מלאי תעדכן גם את יתרת המק\"ט. בדוק/י אצווה ותפוגה לפני האישור.",
                "A receipt updates both the batch and SKU balance. Review the batch and expiry before confirming.",
            ))
            mb1, mb2, mb3, mb4 = st.columns([1.4, 1.8, 1.5, 1.2])
            with mb1:
                mb_amt = st.number_input(
                    L(f"כמות ({w_label})", f"Quantity ({w_label})") if mb_is_w else L("כמות (יח')", "Quantity (units)"),
                    min_value=0.0,
                    value=1.0,
                    step=1.0,
                    key=f"mb_amt_{mb_sku}",
                    disabled=manual_pending,
                )
            with mb2:
                mb_bno = st.text_input(
                    L("מספר אצווה", "Batch number"),
                    value=gen_batch_no(mb_sku),
                    key=f"mb_bno_{mb_sku}",
                    disabled=manual_pending,
                )
            with mb3:
                mb_exp = st.date_input(
                    L("תאריך תפוגה", "Expiry date"),
                    value=date.today() + timedelta(days=365),
                    key=f"mb_exp_{mb_sku}",
                    disabled=manual_pending,
                )
            with mb4:
                mb_noexp = st.checkbox(
                    L("ללא תפוגה", "No expiry"),
                    value=(mb_tp == "PKG"),
                    key=f"mb_noexp_{mb_sku}",
                    disabled=manual_pending,
                )
            review_manual = False
            if not manual_pending:
                review_manual = st.button(
                    L(":material/preview: בדוק כניסה", ":material/preview: Review receipt"),
                    key="mb_review_btn",
                    disabled=mb_amt <= 0,
                    type="primary",
                )
        if review_manual:
            st.session_state[manual_review_key] = True
            st.session_state[manual_version_key] = manual_version + 1
            st.rerun()

        receive_manual = False
        if manual_pending:
            base_amt = mb_amt * w_factor if mb_is_w else mb_amt
            preview_bno = (mb_bno or "").strip() or gen_batch_no(mb_sku)
            preview_exp = "" if mb_noexp else mb_exp.strftime("%Y-%m-%d")
            st.info(L(
                f"קבלה לסקירה: {mb_sku} · {fmt_val(base_amt, mb_is_w)} · אצווה {preview_bno} · תפוגה {format_date(preview_exp, is_he=is_he)}",
                f"Receipt preview: {mb_sku} · {fmt_val(base_amt, mb_is_w)} · batch {preview_bno} · expiry {format_date(preview_exp, is_he=is_he)}",
            ))
            if mb_exp < date.today() and not mb_noexp:
                st.warning(L("תאריך התפוגה כבר עבר; האצווה תהיה חסומה לשימוש FEFO.", "This expiry date is in the past; FEFO will block the batch from use."))
            manual_batch_taken = ctx.batch_exists(mb_sku, preview_bno)
            if manual_batch_taken:
                st.error(L(
                    f"אצווה {preview_bno} כבר קיימת למק\"ט {mb_sku}. בחר/י מספר אצווה אחר.",
                    f"Batch {preview_bno} already exists for SKU {mb_sku}. Choose another batch number.",
                ))
            confirmed_manual = st.checkbox(
                L("בדקתי את פרטי האצווה ואני מאשר/ת לעדכן את המלאי.", "I reviewed the batch details and confirm the stock update."),
                key=manual_confirm_key,
            )
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                receive_manual = st.button(
                    L(":material/add: אשר כניסה", ":material/add: Confirm receipt"),
                    key="mb_confirm_btn",
                    disabled=not confirmed_manual or mb_amt <= 0 or manual_batch_taken,
                    type="primary",
                )
            with cancel_col:
                cancel_manual = st.button(L(":material/close: בטל", ":material/close: Cancel"), key="mb_cancel_btn")
            if cancel_manual:
                st.session_state[manual_review_key] = False
                st.rerun()

        if receive_manual:
            st.session_state[manual_review_key] = False
            push_backup("stock", f"{L('כניסת מלאי', 'Receipt')} {mb_sku}")
            add_batch(mb_sku, preview_bno, base_amt, mb_is_w, preview_exp, "MANUAL")
            now_d = datetime.now().strftime("%Y-%m-%d")
            if mb_is_w:
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ?, last_stock_entry = ? WHERE sku=?",
                             (base_amt, f"{now_d} (+{base_amt/1000:.2f} ק\"ג)", mb_sku))
            else:
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku=?",
                             (base_amt, f"{now_d} (+{base_amt:.0f} יח')", mb_sku))
            conn.commit()
            st.session_state["flash"] = f"נוספה אצווה {preview_bno} למק\"ט {mb_sku}."
            st.rerun()

    with t_b3:
        if not df_b.empty:
            tc1, tc2 = st.columns(2)
            with tc1:
                tr_sku = st.selectbox(L("מק\"ט:", "SKU:"), sorted(df_b["sku"].unique()), key="tr_sku")
            with tc2:
                tr_batch = st.selectbox("Batch #:", list(df_b[df_b["sku"] == tr_sku]["batch_no"]), key=f"tr_batch_{tr_sku}")
            name_map = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn).set_index("sku")

            def trace_df(rows):
                out = []
                for lvl, s, b, qu, wg, mdt, ref in rows:
                    is_w_t = (name_map.loc[s]["item_type"] in ("RAW", "BULK")) if s in name_map.index else False
                    out.append({
                        L("מק\"ט", "SKU"): s,
                        L("רמה", "Level"): lvl,
                        L("פריט", "Item"): name_map.loc[s]["name"] if s in name_map.index else "?",
                        "Batch #": b,
                        L("כמות", "Qty"): fmt_val(float(wg if is_w_t else qu), is_w_t),
                        L("תאריך", "Date"): format_date(mdt, is_he=is_he),
                        L("אסמכתא", "Reference"): ref,
                    })
                return pd.DataFrame(out)

            back_rows = trace_chain(tr_sku, tr_batch, "back")
            fwd_rows = trace_chain(tr_sku, tr_batch, "fwd")
            st.markdown(f"**{L('ממה הוכנה האצווה (אחורה)', 'Made from (backward)')}**")
            if back_rows:
                st.dataframe(trace_df(back_rows), width="stretch", hide_index=True)
            else:
                st.caption(L("אין רשומות (חומר גלם נכנס או מלאי פתיחה).", "No records."))
            st.markdown(f"**{L('לאילו אצוות נכנסה (קדימה)', 'Went into (forward)')}**")
            if fwd_rows:
                st.dataframe(trace_df(fwd_rows), width="stretch", hide_index=True)
            else:
                st.caption(L("האצווה עדיין לא נצרכה באף אצוות מוצר.", "Not consumed yet."))
