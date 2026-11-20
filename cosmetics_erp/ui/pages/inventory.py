from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    eta_week_label = ctx.eta_week_label
    fmt_val = ctx.fmt_val
    get_sku_expiry_summary = ctx.get_sku_expiry_summary
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
        rows_stock_only = ""
        for _, r in df_wh_sub.iterrows():
            s_code = r["sku"]
            stock_str = fmt_val(r["weight_grams"] if is_w_wh else r["qty_units"], is_w_wh)
            exp_info = exp_summary_map.get(s_code, {"batch_no": "-", "expiry_html": "-"})
            rows_stock_only += (
                f"<tr>"
                f"<td><b>{s_code}</b></td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td style='font-size:1.0rem;'><b>{stock_str}</b></td>"
                f"<td>{exp_info['batch_no']}</td>"
                f"<td>{exp_info['expiry_html']}</td>"
                f"</tr>"
            )
        sku_heading = L('מק"ט', "SKU")
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
            f"<th>{sku_heading}</th>"
            f"<th>{L('שם פריט', 'Item Name')}</th>"
            f"<th>{L('כמות מלאי נוכחית', 'Current Stock')} ({w_label if is_w_wh else u_label})</th>"
            f"<th>{L('אצווה פעילה (Batch #)', 'Active Batch #')}</th>"
            f"<th>{L('תאריך תפוגה קרוב (FEFO)', 'Nearest Expiry Date')}</th>"
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
                    f"<td><b>{pr['po_number']}</b></td>"
                    f"<td><b>{pr['sku']}</b> - {name_lookup.get(pr['sku'], '')}</td>"
                    f"<td>{pr['supplier']}</td>"
                    f"<td><b>{amt_po}</b></td>"
                    f"<td>{pr['eta_date']}</td>"
                    f"<td><b>{eta_week_label(pr['eta_date'])}</b></td>"
                    f"<td>{pr['status']}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
                f"<th>{L('מספר הזמנה (PO)', 'PO #')}</th>"
                f"<th>{L('פריט', 'Item')}</th>"
                f"<th>{L('ספק', 'Supplier')}</th>"
                f"<th>{L('כמות מוזמנת', 'Ordered Qty')}</th>"
                f"<th>{L('תאריך הגעה (ETA)', 'ETA Date')}</th>"
                f"<th>{L('שבוע כניסה לסימולטור', 'Simulator Arrival Week')}</th>"
                f"<th>{L('סטטוס', 'Status')}</th>"
                f"</tr></thead><tbody>{po_rows_html}</tbody></table></div>",
                unsafe_allow_html=True
            )

    with sub_tab_sup:
        st.subheader(L("ספקים, ספקים חלופיים ותנועות מלאי אחרונות", "Suppliers & Recent Stock Movements"))
        rows_sup_html = ""
        for _, r in df_wh_sub.iterrows():
            rows_sup_html += (
                f"<tr>"
                f"<td><b>{r['sku']}</b></td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td>{r['main_supplier']}</td>"
                f"<td>{r['alt_suppliers']}</td>"
                f"<td>{r['last_stock_entry']}</td>"
                f"<td>{r['stock_movements']}</td>"
                f"</tr>"
            )
        sku_heading = L('מק"ט', "SKU")
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
            f"<th>{sku_heading}</th>"
            f"<th>{L('שם פריט', 'Item Name')}</th>"
            f"<th>{L('ספק ראשי', 'Main Supplier')}</th>"
            f"<th>{L('ספק חלופי', 'Alt Supplier')}</th>"
            f"<th>{L('כניסת מלאי אחרונה', 'Last Stock Entry')}</th>"
            f"<th>{L('תנועות מלאי אחרונות', 'Recent Movements')}</th>"
            f"</tr></thead><tbody>{rows_sup_html}</tbody></table></div>",
            unsafe_allow_html=True
        )

    with sub_tab_edit:
        df_ed = df_cat.copy()
        df_ed["stock_val"] = df_ed.apply(
            lambda r: round(r["weight_grams"] / w_factor, 3) if r["item_type"] in ["RAW", "BULK"] else round(r["qty_units"], 0),
            axis=1
        )
        edited_cat = st.data_editor(
            df_ed[["last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements", "open_orders", "stock_val", "item_type", "name", "sku"]],
            column_config={
                "sku": st.column_config.TextColumn("מק\"ט", required=True),
                "name": st.column_config.TextColumn("שם פריט", required=True),
                "item_type": st.column_config.SelectboxColumn("מחסן שיוך", options=["RAW", "BULK", "PKG", "FG"], required=True),
                "stock_val": st.column_config.NumberColumn(f"מלאי ({w_label} לחו\"ג ובלק / יח' לאריזה)"),
                "open_orders": st.column_config.TextColumn("הזמנות פתוחות"),
                "stock_movements": st.column_config.TextColumn("תנועות מלאי"),
                "main_supplier": st.column_config.TextColumn("ספק"),
                "alt_suppliers": st.column_config.TextColumn("ספק חלופי"),
                "last_stock_entry": st.column_config.TextColumn("כניסות מלאי אחרונות")
            },
            num_rows="dynamic", use_container_width=True, hide_index=True
        )

        kept_skus = set(str(x).strip() for x in edited_cat["sku"].dropna() if str(x).strip())
        removed_skus = sorted(set(df_cat["sku"]) - kept_skus)
        confirm_cat_del = True
        if removed_skus:
            st.warning(f"שים לב: {len(removed_skus)} פריטים יימחקו אם תשמור: {', '.join(removed_skus)}.")
            confirm_cat_del = st.checkbox("אני מאשר/ת את מחיקת הפריטים האלה", key="cat_del_confirm")

        sb1, sb2 = st.columns(2)
        with sb1:
            save_cat = st.button(":material/save: שמור שינויים בכל המחסנים", disabled=not confirm_cat_del)
        with sb2:
            render_undo_button("stock", "undo_cat")

        if save_cat:
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
