from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.change_review import summarize_editor_changes


def render_catalog_editor(*, L, conn, df_cat, w_factor, w_label, push_backup, reconcile_batches, render_undo_button) -> None:
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
        column_order=[c for c in editor_columns if c not in ("name", "sku")] + ["name", "sku"],
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
        width="stretch",
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
            st.dataframe(preview_rows, width="stretch", hide_index=True)
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
