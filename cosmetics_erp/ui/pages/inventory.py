from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import format_date
from cosmetics_erp.ui.pages.warehouse_update import render_erp_import, render_stock_count
from cosmetics_erp.ui.warehouse_editor import render_catalog_editor


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

    wh_selector = st.radio(
        L("בחר מחסן לתצוגה:", "Select Warehouse:"),
        [
            L("1. מחסן חומר גלם (RAW)", "1. Raw Materials WH"),
            L("2. מחסן בלקים - חומר שהוכן (BULK)", "2. Bulks WH"),
            L("3. מחסן אריזות (PKG)", "3. Packaging WH"),
            L("4. מחסן צבעים (שיער)", "4. Colours WH (hair)"),
        ],
        horizontal=True
    )
    if "4." in wh_selector:
        active_wh_type = "COL"
    elif "1." in wh_selector:
        active_wh_type = "RAW"
    elif "2." in wh_selector:
        active_wh_type = "BULK"
    else:
        active_wh_type = "PKG"
    is_w_wh = active_wh_type in ("RAW", "BULK", "COL")
    if active_wh_type == "COL":
        df_wh_sub = df_cat[(df_cat["item_type"] == "RAW") & (df_cat["primary_warehouse"] == "WH_COLOR")]
    elif active_wh_type == "RAW":
        df_wh_sub = df_cat[(df_cat["item_type"] == "RAW") & (df_cat["primary_warehouse"] != "WH_COLOR")]
    else:
        df_wh_sub = df_cat[df_cat["item_type"] == active_wh_type]
    if active_wh_type == "BULK":
        # Bulk item names start with "בלק" in the data; drop that prefix on this screen only.
        df_wh_sub = df_wh_sub.assign(name=df_wh_sub["name"].astype(str).str.replace(r"^בלק\s+", "", regex=True))

    sub_tab_stock, sub_tab_po, sub_tab_sup, sub_tab_edit, sub_tab_count, sub_tab_import = st.tabs([
        L(":material/inventory: מלאי נוכחי ותאריכי תפוגה", ":material/inventory: Current Stock & Expiry Dates"),
        L(":material/local_shipping: הזמנות רכש (PO)", ":material/local_shipping: Purchase Orders (PO)"),
        L(":material/swap_horiz: ספקים ותנועות מלאי", ":material/swap_horiz: Suppliers & Stock Movements"),
        L(":material/edit_note: עריכה והוספת פריטים", ":material/edit_note: Edit & Add Items"),
        L(":material/fact_check: עדכון לפי ספירה", ":material/fact_check: Update by Count"),
        L(":material/upload_file: ייבוא ERP", ":material/upload_file: ERP Import"),
    ])

    with sub_tab_count:
        render_stock_count(
            L=L, is_he=is_he, conn=conn, df_wh_sub=df_wh_sub, is_w_wh=is_w_wh, w_factor=w_factor, w_label=w_label,
            u_label=u_label, push_backup=push_backup, reconcile_batches=reconcile_batches,
            key_prefix=f"wh_{active_wh_type}",
        )

    with sub_tab_import:
        render_erp_import(L=L, is_he=is_he, conn=conn, w_factor=w_factor, push_backup=push_backup, reconcile_batches=reconcile_batches)

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
                    f"<th scope='row'><b>{escape(str(pr['sku']))}</b></th>"
                    f"<td>{escape(str(name_lookup.get(pr['sku'], '')))}</td>"
                    f"<td><b>{escape(str(pr['po_number']))}</b></td>"
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
                f"<th scope='col'>{L('מק"ט', 'SKU')}</th>"
                f"<th scope='col'>{L('פריט', 'Item')}</th>"
                f"<th scope='col'>{L('מספר הזמנה (PO)', 'PO #')}</th>"
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
        render_catalog_editor(
            L=L, is_he=is_he, conn=conn, df_cat=df_cat, w_factor=w_factor, w_label=w_label, push_backup=push_backup,
            reconcile_batches=reconcile_batches, render_undo_button=render_undo_button,
        )
