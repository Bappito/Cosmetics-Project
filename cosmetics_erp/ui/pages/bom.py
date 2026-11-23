from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.services.bom import PARENT_TYPES, allowed_component_types, to_bom_rows, validate_bom
from cosmetics_erp.ui.context import PageContext
from cosmetics_erp.ui.formatting import sku_first

def _label(sku: str, name: str) -> str:
    return f"{sku} - {name}"


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    push_backup = ctx.push_backup
    is_he = ctx.is_he

    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_bom"]}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "הוספה ועריכה של עצי מוצר. בלק (BULK) מורכב מחומרי גלם (RAW) לכל ק\"ג. מוצר סופי (FG) מורכב מבלקים (BULK) ומאריזות (PKG) לכל יחידה. הבדיקות מונעות שילובים לא נכונים.",
        "Add or edit product trees. A bulk (BULK) is made from raw materials (RAW) per kg. A finished product (FG) is made from bulks (BULK) and packaging (PKG) per unit. Checks block invalid combinations.",
    ))

    catalog = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn)
    types = catalog.set_index("sku")["item_type"].to_dict()
    names = catalog.set_index("sku")["name"].fillna("").to_dict()

    mode = st.radio(
        L("מה לעשות?", "What do you want to do?"),
        ["existing", "new"],
        format_func=lambda v: L("עריכת עץ מוצר קיים", "Edit an existing product tree") if v == "existing"
        else L("עץ מוצר חדש", "New product tree"),
        horizontal=True,
        key="bom_mode",
    )

    if mode == "existing":
        parents = catalog[catalog["item_type"].isin(PARENT_TYPES)]
        if parents.empty:
            st.info(L("אין מוצרים עם עץ אפשרי בקטלוג.", "No products that can have a tree yet."))
            return
        choice = st.selectbox(
            L("בחר מוצר", "Choose a product"),
            [_label(r.sku, r.name) for r in parents.itertuples()],
            key="bom_parent_choice",
        )
        parent_sku = choice.split(" - ")[0]
        parent_name = names.get(parent_sku, "")
        parent_type = types[parent_sku]
        current = pd.read_sql(
            "SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?",
            conn, params=(parent_sku,),
        )
        initial = pd.DataFrame({
            "component_sku": [_label(r.component_sku, names.get(r.component_sku, "")) for r in current.itertuples()],
            "quantity": [
                float(r.req_weight_grams if r.comp_type in ("RAW", "BULK") else r.req_qty_units)
                for r in current.itertuples()
            ],
        })
    else:
        parent_sku = st.text_input(L("מק\"ט המוצר החדש", "New product SKU"), key="bom_new_sku").strip()
        parent_name = st.text_input(L("שם המוצר", "Product name"), key="bom_new_name").strip()
        parent_type = st.selectbox(
            L("סוג המוצר", "Product type"),
            list(PARENT_TYPES),
            format_func=lambda t: "BULK - " + L("בלק (חומר מוכן)", "bulk") if t == "BULK" else "FG - " + L("מוצר סופי", "finished product"),
            key="bom_new_type",
        )
        initial = pd.DataFrame({"component_sku": pd.Series(dtype=str), "quantity": pd.Series(dtype=float)})
        if parent_sku and parent_sku in types:
            st.error(L("המק\"ט הזה כבר קיים בקטלוג.", "This SKU already exists in the catalog."))
            return

    allowed = allowed_component_types(parent_type)
    options = [
        _label(r.sku, r.name)
        for r in catalog[catalog["item_type"].isin(allowed)].itertuples()
    ]
    unit_help = (
        L("גרם לכל ק\"ג של הבלק", "grams per kg of bulk")
        if parent_type == "BULK"
        else L("גרם לכל יחידה (לרכיבי משקל) או יחידות (לאריזות)", "grams per unit (weight parts) or units (packaging)")
    )

    st.markdown(f"**{L('רכיבי העץ', 'Components')}** — {L('סוג המוצר', 'type')}: {parent_type}")
    edited = st.data_editor(
        initial,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"bom_editor_{mode}_{parent_sku}",
        column_order=sku_first(initial.columns, is_he),
        column_config={
            "component_sku": st.column_config.SelectboxColumn(
                L("רכיב", "Component"), options=options, required=True, width="large"
            ),
            "quantity": st.column_config.NumberColumn(
                L("כמות", "Quantity"), help=unit_help, min_value=0.0, format="%.3f"
            ),
        },
    )

    rows = []
    for r in edited.itertuples():
        comp = str(r.component_sku or "").split(" - ")[0].strip()
        if not comp and (pd.isna(r.quantity) or r.quantity in (None, 0)):
            continue
        rows.append({"component_sku": comp, "quantity": r.quantity})

    if mode == "new":
        # Only the new SKU and name are checked here; the tree rules run below.
        if parent_sku and not parent_name:
            st.error(L("יש להזין שם למוצר החדש.", "Enter a name for the new product."))

    errors = list(validate_bom(parent_sku, parent_type, rows, types)) if parent_sku else [
        L("יש להזין מק\"ט למוצר.", "Enter a SKU for the product.")
    ]
    if mode == "new" and not parent_name:
        errors.append(L("יש להזין שם למוצר החדש.", "Enter a name for the new product."))
    for error in errors:
        st.error(error)

    if not errors:
        preview = pd.DataFrame([
                {
                    L("רכיב", "Component"): row["component_sku"],
                    L("שם", "Name"): names.get(row["component_sku"], ""),
                    L("סוג", "Type"): types.get(row["component_sku"], ""),
                    L("כמות", "Quantity"): row["quantity"],
                }
                for row in rows
            ])
        st.dataframe(preview, column_order=sku_first(preview.columns, is_he), hide_index=True)

    confirm = st.checkbox(
        L("בדקתי את העץ ואני מאשר/ת לשמור אותו.", "I reviewed the tree and confirm saving it."),
        key=f"bom_confirm_{mode}_{parent_sku}",
    )
    if st.button(L(":material/save: שמור עץ מוצר", ":material/save: Save product tree"), key="bom_save", type="primary",
                 disabled=bool(errors) or not confirm):
        push_backup("stock", L(f"עץ מוצר {parent_sku}", f"Product tree {parent_sku}"))
        if mode == "new":
            conn.execute(
                "INSERT INTO Catalog (sku, name, item_type, primary_warehouse) VALUES (?,?,?,?)",
                (parent_sku, parent_name, parent_type, "WH_BULK" if parent_type == "BULK" else "WH_FG"),
            )
            if parent_type == "FG":
                conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (parent_sku,))
        conn.execute("DELETE FROM BOM WHERE parent_sku = ?", (parent_sku,))
        conn.executemany(
            "INSERT INTO BOM (parent_sku, component_sku, comp_type, req_qty_units, req_weight_grams) VALUES (?,?,?,?,?)",
            to_bom_rows(parent_sku, rows, types, parent_type),
        )
        conn.commit()
        st.session_state["flash"] = L(f"עץ המוצר {parent_sku} נשמר ({len(rows)} רכיבים).", f"Saved the tree for {parent_sku} ({len(rows)} components).")
        st.rerun()
