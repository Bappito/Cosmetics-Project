from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.change_review import summarize_editor_changes
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_date


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    eta_week_label = ctx.eta_week_label
    fmt_val = ctx.fmt_val
    get_sku_expiry_summary = ctx.get_sku_expiry_summary
    is_he = ctx.is_he
    push_backup = ctx.push_backup
    reconcile_batches = ctx.reconcile_batches
    render_undo_button = ctx.render_undo_button
    u_label = ctx.u_label
    w_factor = ctx.w_factor
    w_label = ctx.w_label
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_inv"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
    df_po_all = pd.read_sql("SELECT * FROM PurchaseOrders WHERE status NOT IN ('Received','Cancelled') ORDER BY eta_date ASC", conn)
    exp_summary_map = get_sku_expiry_summary()

    c1, c2, c3 = st.columns(3)
    raw_tot = fmt_val(df_cat[df_cat["item_type"] == "RAW"]["weight_grams"].sum(), True)
    bulk_tot = fmt_val(df_cat[df_cat["item_type"] == "BULK"]["weight_grams"].sum(), True)
    pkg_tot = fmt_val(df_cat[df_cat["item_type"] == "PKG"]["qty_units"].sum(), False)

    c1.metric(L("מחסן חומר גלם (RAW)", "Raw Materials WH"), raw_tot)
    c2.metric(L("מחסן בלקים - חומר מוכן (BULK)", "Bulks WH"), bulk_tot)
    c3.metric(L("מחסן אריזות (PKG)", "Packaging WH"), pkg_tot)

    wh_selector = st.radio(
        L("בחר מחסן לתצוגה:", "Select Warehouse:"),
        [
            L("1. מחסן חומר גלם (RAW)", "1. Raw Materials WH"),
            L("2. מחסן בלקים - חומר שהוכן (BULK)", "2. Bulks WH"),
            L("3. מחסן אריזות (PKG)", "3. Packaging WH")
        ],
        horizontal=True
    )
    active_wh_type = "RAW" if "1." in wh_selector else ("BULK" if "2." in wh_selector else "PKG")
    is_w_wh = active_wh_type in ("RAW", "BULK")
    df_wh_sub = df_cat[df_cat["item_type"] == active_wh_type]

    sub_tab_stock, sub_tab_po, sub_tab_sup, sub_tab_edit = st.tabs([
        L(":material/inventory: מלאי נוכחי ותאריכי תפוגה", ":material/inventory: Current Stock & Expiry Dates"),
        L(":material/local_shipping: הזמנות רכש (PO)", ":material/local_shipping: Purchase Orders (PO)"),
        L(":material/swap_horiz: ספקים ותנועות מלאי", ":material/swap_horiz: Suppliers & Stock Movements"),
        L(":material/edit_note: עריכה והוספת פריטים", ":material/edit_note: Edit & Add Items")
    ])

    with sub_tab_stock:
        st.subheader(L("יתרת מלאי נוכחית ותאריכי תפוגה (FEFO)", "Current Stock & Expiry Dates (FEFO)"))
        stock_query = st.text_input(
            L("חיפוש לפי מק\"ט או שם פריט", "Search by SKU or item name"),
            key=f"inventory_stock_search_{active_wh_type}",
            placeholder=L("הקלד/י מק\"ט או שם", "Type an SKU or name"),
        ).strip()
        df_wh_view = df_wh_sub
        if stock_query:
            matches = (
                df_wh_view["sku"].astype(str).str.contains(stock_query, case=False, na=False, regex=False)
                | df_wh_view["name"].astype(str).str.contains(stock_query, case=False, na=False, regex=False)
            )
            df_wh_view = df_wh_view[matches]
        st.caption(L(
            f"מוצגים {len(df_wh_view)} מתוך {len(df_wh_sub)} פריטים",
            f"Showing {len(df_wh_view)} of {len(df_wh_sub)} items",
        ))
        rows_stock_only = ""
        for _, r in df_wh_view.iterrows():
            raw_sku = str(r["sku"])
            s_code = escape(raw_sku)
            stock_str = fmt_val(r["weight_grams"] if is_w_wh else r["qty_units"], is_w_wh)
            exp_info = exp_summary_map.get(raw_sku, {"batch_no": "-", "expiry_html": "-"})
            rows_stock_only += (
                f"<tr>"
                f"<th scope='row'><b>{s_code}</b></th>"
                f"<td><b>{escape(str(r['name']))}</b></td>"
                f"<td style='font-size:1.0rem;'><b>{stock_str}</b></td>"
                f"<td>{escape(str(exp_info['batch_no']))}</td>"
                f"<td>{exp_info['expiry_html']}</td>"
                f"</tr>"
            )
        if df_wh_view.empty:
            st.info(L("לא נמצאו פריטים התואמים לחיפוש.", "No items match this search."))
        sku_heading = L('מק"ט', "SKU")
        stock_caption = L("מלאי נוכחי לפי מק\"ט ותפוגה", "Current stock by SKU and expiry")
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'>"
            f"<caption class='sr-only'>{stock_caption}</caption>"
            f"<thead><tr>"
            f"<th scope='col'>{sku_heading}</th>"
            f"<th scope='col'>{L('שם פריט', 'Item Name')}</th>"
            f"<th scope='col'>{L('כמות מלאי נוכחית', 'Current Stock')} ({w_label if is_w_wh else u_label})</th>"
            f"<th scope='col'>{L('אצווה פעילה (Batch #)', 'Active Batch #')}</th>"
            f"<th scope='col'>{L('תאריך תפוגה קרוב (FEFO)', 'Nearest Expiry Date')}</th>"
            f"</tr></thead><tbody>{rows_stock_only}</tbody></table></div>",
            unsafe_allow_html=True
        )

    with sub_tab_po:
        st.subheader(L("הזמנות רכש פתוחות למחסן זה", "Open Purchase Orders for this Warehouse"))
        wh_skus = set(df_wh_sub["sku"])
        df_po_wh = df_po_all[df_po_all["sku"].isin(wh_skus)]
        if df_po_wh.empty:
            st.info(L("אין הזמנות רכש פתוחות למחסן זה כרגע.", "No open purchase orders for this warehouse."))
        else:
            po_rows_html = ""
            name_lookup = df_wh_sub.set_index("sku")["name"].to_dict()
            for _, pr in df_po_wh.iterrows():
                amt_po = fmt_val(float(pr["order_weight_grams"] if is_w_wh else pr["order_qty_units"]), is_w_wh)
                po_rows_html += (
                    f"<tr>"
                    f"<td><b>{escape(str(pr['po_number']))}</b></td>"
                    f"<td><b>{escape(str(pr['sku']))}</b> - {escape(str(name_lookup.get(pr['sku'], '')))}</td>"
                    f"<td>{escape(str(pr['supplier']))}</td>"
                    f"<td><b>{amt_po}</b></td>"
                    f"<td>{format_date(pr['eta_date'], is_he=is_he)}</td>"
                    f"<td><b>{eta_week_label(pr['eta_date'])}</b></td>"
                    f"<td><span class='status-badge'>{escape(str(pr['status']))}</span></td>"
                    f"</tr>"
                )
            st.markdown(
                f"<div class='table-responsive'><table class='rtl-table'>"
                f"<caption class='sr-only'>{L('הזמנות רכש פתוחות למחסן', 'Open purchase orders by warehouse')}</caption>"
                f"<thead><tr>"
                f"<th scope='col'>{L('מספר הזמנה (PO)', 'PO #')}</th>"
                f"<th scope='col'>{L('פריט', 'Item')}</th>"
                f"<th scope='col'>{L('ספק', 'Supplier')}</th>"
                f"<th scope='col'>{L('כמות מוזמנת', 'Ordered Qty')}</th>"
                f"<th scope='col'>{L('תאריך הגעה (ETA)', 'ETA Date')}</th>"
                f"<th scope='col'>{L('שבוע כניסה לסימולטור', 'Simulator Arrival Week')}</th>"
                f"<th scope='col'>{L('סטטוס', 'Status')}</th>"
                f"</tr></thead><tbody>{po_rows_html}</tbody></table></div>",
                unsafe_allow_html=True
            )

    with sub_tab_sup:
        st.subheader(L("ספקים, ספקים חלופיים ותנועות מלאי אחרונות", "Suppliers & Recent Stock Movements"))
        rows_sup_html = ""
        for _, r in df_wh_sub.iterrows():
            rows_sup_html += (
                f"<tr>"
                f"<th scope='row'><b>{escape(str(r['sku']))}</b></th>"
                f"<td><b>{escape(str(r['name']))}</b></td>"
                f"<td>{escape(str(r['main_supplier']))}</td>"
                f"<td>{escape(str(r['alt_suppliers']))}</td>"
                f"<td>{escape(str(r['last_stock_entry']))}</td>"
                f"<td>{escape(str(r['stock_movements']))}</td>"
                f"</tr>"
            )
        sku_heading = L('מק"ט', "SKU")
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'>"
            f"<caption class='sr-only'>{L('ספקים ותנועות לפי פריט', 'Suppliers and movements by item')}</caption>"
            f"<thead><tr>"
            f"<th scope='col'>{sku_heading}</th>"
            f"<th scope='col'>{L('שם פריט', 'Item Name')}</th>"
            f"<th scope='col'>{L('ספק ראשי', 'Main Supplier')}</th>"
            f"<th scope='col'>{L('ספק חלופי', 'Alt Supplier')}</th>"
            f"<th scope='col'>{L('כניסת מלאי אחרונה', 'Last Stock Entry')}</th>"
            f"<th scope='col'>{L('תנועות מלאי אחרונות', 'Recent Movements')}</th>"
            f"</tr></thead><tbody>{rows_sup_html}</tbody></table></div>",
            unsafe_allow_html=True
        )

    with sub_tab_edit:
        df_ed = df_cat.copy()
        df_ed["stock_val"] = df_ed.apply(
            lambda r: round(r["weight_grams"] / w_factor, 3) if r["item_type"] in ["RAW", "BULK"] else round(r["qty_units"], 0),
            axis=1
        )
        editor_columns = [
            "last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements",
            "open_orders", "stock_val", "item_type", "name", "sku",
        ]
        catalog_review_key = "catalog_review_pending"
        catalog_review_version_key = "catalog_review_version"
        catalog_review_version = st.session_state.get(catalog_review_version_key, 0)
        catalog_confirm_key = f"catalog_review_confirmed_{catalog_review_version}"
        edited_cat = st.data_editor(
            df_ed[editor_columns],
            column_config={
                "sku": st.column_config.TextColumn(L("מק\"ט", "SKU"), required=True),
                "name": st.column_config.TextColumn(L("שם פריט", "Item name"), required=True),
                "item_type": st.column_config.SelectboxColumn(L("סוג פריט", "Item type"), options=["RAW", "BULK", "PKG", "FG"], required=True),
                "stock_val": st.column_config.NumberColumn(L(f"מלאי ({w_label} לחומר/בלק, יחידות לאריזה)", f"Stock ({w_label} for material/bulk, units for packaging)"), min_value=0),
                "open_orders": st.column_config.TextColumn(L("הזמנות פתוחות", "Open orders")),
                "stock_movements": st.column_config.TextColumn(L("תנועות מלאי", "Stock movements")),
                "main_supplier": st.column_config.TextColumn(L("ספק ראשי", "Main supplier")),
                "alt_suppliers": st.column_config.TextColumn(L("ספקים חלופיים", "Alternate suppliers")),
                "last_stock_entry": st.column_config.TextColumn(L("כניסת מלאי אחרונה", "Last stock receipt"))
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="catalog_editor",
            disabled=st.session_state.get(catalog_review_key, False),
        )

        sku_values = edited_cat["sku"].fillna("").astype(str).str.strip()
        rows_with_sku = sku_values.ne("")
        duplicate_skus = sorted(sku_values[rows_with_sku & sku_values.duplicated(keep=False)].unique())
        invalid_names = edited_cat.loc[rows_with_sku, "name"].fillna("").astype(str).str.strip().eq("")
        invalid_types = edited_cat.loc[rows_with_sku, "item_type"].isin(["RAW", "BULK", "PKG", "FG"]).eq(False)
        stock_values = pd.to_numeric(edited_cat.loc[rows_with_sku, "stock_val"], errors="coerce")
        invalid_stock = stock_values.isna() | (stock_values < 0)
        validation_errors = []
        if duplicate_skus:
            validation_errors.append(L(
                f"יש מק\"טים כפולים: {', '.join(duplicate_skus)}.",
                f"Duplicate SKUs: {', '.join(duplicate_skus)}.",
            ))
        if invalid_names.any():
            validation_errors.append(L("לכל מק\"ט נדרש שם פריט.", "Every SKU needs an item name."))
        if invalid_types.any():
            validation_errors.append(L("יש לבחור סוג פריט תקין לכל שורה.", "Select a valid item type for each row."))
        if invalid_stock.any():
            validation_errors.append(L("המלאי חייב להיות מספר שאינו שלילי.", "Stock values must be valid non-negative numbers."))
        for error in validation_errors:
            st.error(error)

        catalog_changes = summarize_editor_changes(
            df_ed[editor_columns], edited_cat[editor_columns], "sku", editor_columns[:-1]
        )
        added_skus, removed_skus, changed_rows_skus = catalog_changes
        catalog_has_changes = bool(any(catalog_changes))

        sb1, sb2 = st.columns(2)
        with sb1:
            review_cat = st.button(
                L(":material/preview: בדוק שינויים", ":material/preview: Review changes"),
                key="catalog_review_button",
                disabled=bool(validation_errors) or not catalog_has_changes or st.session_state.get(catalog_review_key, False),
                type="primary",
            )
        with sb2:
            if not st.session_state.get(catalog_review_key, False):
                render_undo_button("stock", "undo_cat")

        if review_cat:
            st.session_state[catalog_review_key] = True
            st.session_state[catalog_review_version_key] = catalog_review_version + 1
            st.rerun()

        save_cat = False
        if st.session_state.get(catalog_review_key, False):
            st.info(L(
                f"סקירת שינויים: {len(added_skus)} פריטים חדשים, {len(changed_rows_skus)} עודכנו, {len(removed_skus)} יימחקו.",
                f"Change review: {len(added_skus)} added, {len(changed_rows_skus)} changed, {len(removed_skus)} will be removed.",
            ))
            if removed_skus:
                st.warning(L(
                    f"הפריטים הבאים יימחקו: {', '.join(removed_skus)}",
                    f"The following SKUs will be deleted: {', '.join(removed_skus)}",
                ))
            preview_skus = set(added_skus) | set(changed_rows_skus)
            preview_rows = edited_cat[sku_values.isin(preview_skus)]
            if not preview_rows.empty:
                st.dataframe(preview_rows, use_container_width=True, hide_index=True)
            confirmed_cat = st.checkbox(
                L("בדקתי את התצוגה המקדימה ואני מאשר/ת לשמור את השינויים.", "I reviewed the preview and confirm these changes."),
                key=catalog_confirm_key,
            )
            confirm_col, cancel_col = st.columns(2)
            with confirm_col:
                save_cat = st.button(
                    L(":material/save: אשר ושמור", ":material/save: Confirm and save"),
                    key="catalog_confirm_button",
                    disabled=not confirmed_cat or bool(validation_errors),
                    type="primary",
                )
            with cancel_col:
                cancel_catalog = st.button(L(":material/close: בטל", ":material/close: Cancel"), key="catalog_cancel_button")
            if cancel_catalog:
                st.session_state[catalog_review_key] = False
                st.rerun()

        if save_cat:
            st.session_state[catalog_review_key] = False
            push_backup("stock", L("שמירת עורך מחסנים", "Warehouse editor save"))
            old_cat = df_cat.set_index("sku").to_dict("index")
            conn.execute("DELETE FROM Catalog")
            for _, r in edited_cat.iterrows():
                if pd.notna(r["sku"]) and str(r["sku"]).strip():
                    sku_s = str(r["sku"]).strip()
                    tp = str(r["item_type"] or "RAW")
                    v_num = float(r["stock_val"] or 0)
                    w_g = (v_num * w_factor) if tp in ["RAW", "BULK"] else 0.0
                    q_u = 0.0 if tp in ["RAW", "BULK"] else v_num
                    wh_k = "WH_RAW" if tp == "RAW" else ("WH_BULK" if tp == "BULK" else ("WH_PACK" if tp == "PKG" else "WH_FG"))
                    old = old_cat.get(sku_s, {})
                    conn.execute("""
                        INSERT INTO Catalog (sku, name, item_type, qty_units, weight_grams, open_orders, stock_movements, main_supplier, alt_suppliers, last_stock_entry, primary_warehouse,
                                             item_price, min_order_qty, last_purchase_price, sap_code)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (sku_s, str(r["name"]), tp, q_u, w_g, str(r["open_orders"] or "0"),
                          str(r["stock_movements"] or "-"), str(r["main_supplier"] or ""), str(r["alt_suppliers"] or ""),
                          str(r["last_stock_entry"] or "-"), wh_k,
                          float(old.get("item_price", 0) or 0), float(old.get("min_order_qty", 1) or 1),
                          float(old.get("last_purchase_price", 0) or 0), str(old.get("sap_code", "") or "")))
            conn.commit()
            reconcile_batches()
            st.session_state["flash"] = "המחסנים עודכנו בהצלחה!"
            st.rerun()
