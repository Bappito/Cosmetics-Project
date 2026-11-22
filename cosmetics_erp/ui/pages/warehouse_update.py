from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from cosmetics_erp.services.erp_import import build_po_rows, build_stock_rows, guess_column, read_table

WEIGHT_TYPES = ("RAW", "BULK")


def _apply_stock(conn, rows: pd.DataFrame, cat: pd.DataFrame, w_factor: float, reconcile_batches) -> None:
    """Set catalog balances to the counted values, then reconcile batches (which logs ADJUST movements)."""
    types = cat.set_index("sku")["item_type"].to_dict()
    for row in rows.itertuples():
        if types.get(row.sku) in WEIGHT_TYPES:
            conn.execute("UPDATE Catalog SET weight_grams = ?, last_stock_entry = ? WHERE sku = ?",
                         (float(row.counted), datetime.now().strftime("%Y-%m-%d") + " (ספירה)", row.sku))
        else:
            conn.execute("UPDATE Catalog SET qty_units = ?, last_stock_entry = ? WHERE sku = ?",
                         (float(row.counted), datetime.now().strftime("%Y-%m-%d") + " (ספירה)", row.sku))
    conn.commit()
    reconcile_batches()


def render_stock_count(
    *,
    L,
    conn,
    df_wh_sub: pd.DataFrame,
    is_w_wh: bool,
    w_factor: float,
    w_label: str,
    u_label: str,
    push_backup,
    reconcile_batches,
    key_prefix: str,
) -> None:
    """Physical count: enter what was counted per SKU, review the differences, then apply."""
    st.subheader(L("עדכון מלאי לפי ספירה", "Update stock by physical count"))
    st.caption(L(
        "הזן/י את הכמות שנספרה בפועל לכל מק\"ט. רק שורות שהשתנו יעודכנו, ויירשם תיעוד תנועה.",
        "Enter the physically counted quantity for each SKU. Only changed rows are updated, and each change is logged as a movement.",
    ))
    if df_wh_sub.empty:
        st.info(L("אין פריטים במחסן זה.", "No items in this warehouse."))
        return

    unit = w_label if is_w_wh else u_label
    base = pd.DataFrame({
        "sku": df_wh_sub["sku"].astype(str),
        "name": df_wh_sub["name"].astype(str),
        "system": (df_wh_sub["weight_grams"] / w_factor if is_w_wh else df_wh_sub["qty_units"]).astype(float).round(3),
    })
    edited = st.data_editor(
        base.assign(counted=base["system"]),
        column_config={
            "sku": st.column_config.TextColumn(L("מק\"ט", "SKU"), disabled=True),
            "name": st.column_config.TextColumn(L("שם פריט", "Item"), disabled=True),
            "system": st.column_config.NumberColumn(L(f"במערכת ({unit})", f"In system ({unit})"), disabled=True, format="%.3f"),
            "counted": st.column_config.NumberColumn(L(f"נספר ({unit})", f"Counted ({unit})"), min_value=0.0, format="%.3f"),
        },
        hide_index=True,
        key=f"{key_prefix}_count_editor",
    )
    edited = edited.copy()
    edited["counted"] = pd.to_numeric(edited["counted"], errors="coerce")
    changed = edited[(edited["counted"] - edited["system"]).abs() > 1e-6]
    invalid = edited["counted"].isna() | (edited["counted"] < 0)

    if invalid.any():
        st.error(L("יש לתקן ערכי ספירה שליליים או ריקים.", "Fix blank or negative counted values."))
    if changed.empty:
        st.caption(L("אין שינויים לשמירה.", "No changes to save."))
        return

    st.dataframe(changed.assign(difference=(changed["counted"] - changed["system"]).round(3))[["sku", "name", "system", "counted", "difference"]], hide_index=True)
    confirm = st.checkbox(L("בדקתי את ההפרשים ואני מאשר/ת את העדכון.", "I reviewed the differences and confirm the update."), key=f"{key_prefix}_count_confirm")
    if st.button(L(":material/save: עדכן מלאי לפי הספירה", ":material/save: Apply count"), key=f"{key_prefix}_count_apply", type="primary", disabled=not confirm or invalid.any()):
        push_backup("stock", L("ספירת מחסן", "Warehouse count"))
        scaled = changed.copy()
        scaled["counted"] = scaled["counted"] * (w_factor if is_w_wh else 1.0)
        cat_view = pd.read_sql("SELECT sku, item_type FROM Catalog", conn)
        _apply_stock(conn, scaled[["sku", "counted"]], cat_view, w_factor, reconcile_batches)
        st.session_state["flash"] = L(f"עודכנו {len(changed)} פריטים לפי הספירה.", f"Updated {len(changed)} items from the count.")
        st.rerun()


def render_erp_import(
    *,
    L,
    conn,
    w_factor: float,
    push_backup,
    reconcile_batches,
) -> None:
    """Upload an ERP export (SAP, Priority, or any CSV/Excel), map its columns, review, then apply."""
    st.subheader(L("ייבוא מערכת ERP (SAP / Priority)", "Import from ERP (SAP / Priority)"))
    st.caption(L(
        "העלה/י קובץ CSV או Excel שיוצא מהמערכת. בחר/י איזו עמודה מתאימה לכל שדה, בדוק/י את התצוגה המקדימה ואשר/י. לפני העדכון נשמר גיבוי.",
        "Upload a CSV or Excel export from your system. Map each field to a column, review the preview, and confirm. A backup is saved before any change.",
    ))

    cat = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn)
    known = set(cat["sku"].astype(str))
    weight_skus = set(cat.loc[cat["item_type"].isin(WEIGHT_TYPES), "sku"].astype(str))

    upload = st.file_uploader(L("קובץ ייצוא", "Export file"), type=["csv", "xlsx", "xls"], key="erp_upload")
    if upload is None:
        st.info(L("טרם הועלה קובץ.", "No file uploaded yet."))
        return
    try:
        df = read_table(upload.name, upload.getvalue())
    except ValueError as exc:
        st.error(str(exc))
        return
    st.caption(L(f"נקראו {len(df)} שורות.", f"Read {len(df)} rows."))

    kind = st.radio(
        L("סוג הייבוא", "Import type"),
        ["stock", "po"],
        format_func=lambda v: L("יתרות מלאי (ספירה / מערכת)", "Stock balances") if v == "stock" else L("הזמנות רכש (PO)", "Purchase orders"),
        horizontal=True,
        key="erp_kind",
    )
    columns = [""] + list(df.columns)

    def pick(field: str, label: str, required: bool = True):
        guessed = guess_column(list(df.columns), field) or ""
        index = columns.index(guessed) if guessed in columns else 0
        return st.selectbox(
            label + ("" if required else L(" (לא חובה)", " (optional)")),
            columns, index=index, key=f"erp_map_{kind}_{field}",
        ) or None

    m1, m2, m3 = st.columns(3)
    with m1:
        sku_col = pick("sku", L("עמודת מק\"ט", "SKU column"))
    with m2:
        qty_col = pick("qty", L("עמודת כמות", "Quantity column"))
    with m3:
        unit_choice = st.radio(
            L("יחידת כמות לפריטי משקל", "Quantity unit for weight items"),
            ["kg", "g"], horizontal=True, key="erp_unit",
            format_func=lambda v: L("ק\"ג", "kg") if v == "kg" else L("גרם", "g"),
        )
    factor = 1000.0 if unit_choice == "kg" else 1.0

    mapping = {"sku": sku_col, "qty": qty_col}
    if kind == "po":
        p1, p2, p3, p4 = st.columns(4)
        with p1:
            mapping["po_number"] = pick("po_number", L("עמודת מספר PO", "PO number column"))
        with p2:
            mapping["supplier"] = pick("supplier", L("עמודת ספק", "Supplier column"), required=False)
        with p3:
            mapping["eta"] = pick("eta", L("עמודת תאריך הגעה", "ETA column"), required=False)
        with p4:
            pass

    if not all(mapping.get(k) for k in (["sku", "qty"] + (["po_number"] if kind == "po" else []))):
        st.warning(L("יש למפות את כל השדות הנדרשים.", "Map all required fields."))
        return

    if kind == "stock":
        rows, errors = build_stock_rows(df, mapping, known, weight_skus, factor)
        preview = rows.rename(columns={"sku": "SKU", "counted": L("כמות שתיקבע", "New balance (base units)")}) if not rows.empty else rows
    else:
        po_rows, errors = build_po_rows(df, mapping, known, weight_skus, factor)
        preview = pd.DataFrame(po_rows)
        if not preview.empty:
            preview = preview.rename(columns={
                "po_number": L("מספר PO", "PO"), "sku": L("מק\"ט", "SKU"),
                "supplier": L("ספק", "Supplier"), "qty_base": L("כמות (בסיס)", "Qty (base)"), "eta": "ETA",
            })
            sku_name = L("מק\"ט", "SKU")
            preview = preview[[sku_name] + [c for c in preview.columns if c != sku_name]]

    for error in errors:
        st.error(error)
    if preview.empty:
        st.info(L("אין שורות תקינות לתצוגה.", "No valid rows to preview."))
        return

    st.markdown(f"**{L('תצוגה מקדימה', 'Preview')}** — {len(preview)} {L('שורות', 'rows')}")
    st.dataframe(preview, hide_index=True)

    confirm = st.checkbox(L("בדקתי את התצוגה המקדימה ואני מאשר/ת את הייבוא.", "I reviewed the preview and confirm the import."), key=f"erp_confirm_{kind}")
    if st.button(L(":material/upload: ייבא לנתוני המערכת", ":material/upload: Import into the system"), key=f"erp_apply_{kind}", type="primary", disabled=bool(errors) or not confirm):
        push_backup("stock", L("ייבוא ERP", "ERP import"))
        if kind == "stock":
            cat_view = pd.read_sql("SELECT sku, item_type FROM Catalog", conn)
            _apply_stock(conn, rows, cat_view, w_factor, reconcile_batches)
            message = L(f"עודכנו {len(rows)} מק\"טים מקובץ ה-ERP.", f"Updated {len(rows)} SKUs from the ERP file.")
        else:
            for row in po_rows:
                is_w = row["sku"] in weight_skus
                existing = conn.execute("SELECT po_id FROM PurchaseOrders WHERE po_number = ?", (row["po_number"],)).fetchone()
                qty_units = 0.0 if is_w else row["qty_base"]
                qty_grams = row["qty_base"] if is_w else 0.0
                if existing:
                    conn.execute(
                        "UPDATE PurchaseOrders SET sku=?, supplier=?, order_qty_units=?, order_weight_grams=?, eta_date=? WHERE po_id=?",
                        (row["sku"], row["supplier"], qty_units, qty_grams, row["eta"], existing[0]),
                    )
                else:
                    conn.execute(
                        "INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, eta_date, target_wh, status) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (row["po_number"], row["sku"], row["supplier"], qty_units, qty_grams, row["eta"], "WH_RAW", "In Transit"),
                    )
            conn.commit()
            message = L(f"יובאו {len(po_rows)} שורות הזמנה.", f"Imported {len(po_rows)} order rows.")
        st.session_state["flash"] = message
        st.rerun()
