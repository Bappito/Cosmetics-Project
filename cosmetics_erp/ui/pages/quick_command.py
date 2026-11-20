from __future__ import annotations

import re

import streamlit as st

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    push_backup = ctx.push_backup
    reconcile_batches = ctx.reconcile_batches
    render_undo_button = ctx.render_undo_button
    fmt_val = ctx.fmt_val
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_ai"]}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "הזן/י כמות ויחידה מפורשות ואחריהן מק\"ט, לדוגמה: `הוסף 5 קילו ל-1001` או `הוסף 300 יחידות ל-3001`.",
        "Enter an amount and explicit unit followed by an SKU, e.g. `add 5 kg to 1001` or `add 300 units to 3001`.",
    ))
    render_undo_button("stock", "undo_agent")
    pending_key = "quick_command_pending"
    pending = st.session_state.get(pending_key)
    cmd_in = st.chat_input(
        L("כתוב פקודת מלאי לסקירה...", "Enter a stock command to review..."),
        disabled=bool(pending),
    )
    if cmd_in:
        nums = re.findall(r"(-?\d+(?:[.,]\d+)?)", cmd_in)
        if len(nums) < 2:
            st.error(L(
                "הפקודה צריכה לכלול כמות, יחידה ומק\"ט.",
                "The command must include a quantity, unit, and SKU.",
            ))
        else:
            amount = float(nums[0].replace(",", "."))
            sku = nums[-1]
            if amount <= 0:
                st.error(L("הכמות חייבת להיות גדולה מאפס.", "The quantity must be greater than zero."))
            else:
                item = conn.execute(
                    "SELECT name, item_type, qty_units, weight_grams FROM Catalog WHERE sku=?",
                    (sku,),
                ).fetchone()
                if not item:
                    st.error(L(f"מק\"ט {sku} לא קיים בקטלוג.", f"SKU {sku} was not found in the catalog."))
                else:
                    normalized = cmd_in.casefold()
                    is_weight_item = item[1] in ("RAW", "BULK")
                    is_kg = "קילו" in normalized or "ק\"ג" in normalized or "kg" in normalized
                    is_grams = "גרם" in normalized or "gram" in normalized or re.search(r"\bg\b", normalized) is not None
                    has_units = "יחיד" in normalized or "יח'" in normalized or "unit" in normalized
                    unit_kind = "kg" if is_kg else ("g" if is_grams else ("units" if has_units else None))
                    if is_weight_item and unit_kind not in ("kg", "g"):
                        st.error(L(
                            "למק\"ט משקלי יש לציין קילו או גרם.",
                            "For a weight-based SKU, specify kg or grams.",
                        ))
                    elif not is_weight_item and unit_kind != "units":
                        st.error(L(
                            "למק\"ט יחידות יש לציין יחידות (units).",
                            "For a unit-based SKU, specify units.",
                        ))
                    elif unit_kind == "units" and not amount.is_integer():
                        st.error(L("כמות ביחידות חייבת להיות מספר שלם.", "Unit quantities must be whole numbers."))
                    else:
                        added_base = amount * 1000.0 if unit_kind == "kg" else amount
                        st.session_state[pending_key] = {
                            "sku": sku,
                            "name": item[0],
                            "item_type": item[1],
                            "amount": amount,
                            "unit": unit_kind,
                            "added_base": added_base,
                            "is_weight": is_weight_item,
                            "command": cmd_in,
                        }
                        st.rerun()

    pending = st.session_state.get(pending_key)
    if pending:
        current = conn.execute(
            "SELECT qty_units, weight_grams FROM Catalog WHERE sku=?",
            (pending["sku"],),
        ).fetchone()
        if current is None:
            st.error(L("המק\"ט הוסר מהקטלוג. בטל/י את הפקודה.", "The SKU was removed from the catalog. Cancel this command."))
            if st.button(L(":material/close: בטל פקודה", ":material/close: Cancel command"), key="quick_command_missing_cancel"):
                st.session_state[pending_key] = None
                st.rerun()
        else:
            is_weight = pending["is_weight"]
            current_base = float(current[1] if is_weight else current[0])
            next_base = current_base + pending["added_base"]
            amount_text = f"{pending['amount']:g} {pending['unit']}"
            with st.container(border=True):
                st.markdown(f"**{L('תצוגה מקדימה של שינוי מלאי', 'Stock change preview')}**")
                st.write(L(
                    f"{pending['sku']} · {pending['name']} · הוספה של {amount_text}",
                    f"{pending['sku']} · {pending['name']} · add {amount_text}",
                ))
                st.caption(L(
                    f"יתרה: {fmt_val(current_base, is_weight)} ← {fmt_val(next_base, is_weight)}",
                    f"Balance: {fmt_val(current_base, is_weight)} → {fmt_val(next_base, is_weight)}",
                ))
                version_key = "quick_command_review_version"
                version = st.session_state.get(version_key, 0)
                confirm_key = f"quick_command_review_confirmed_{version}"
                confirmed = st.checkbox(
                    L("בדקתי את השינוי ואני מאשר/ת לעדכן את המלאי.", "I reviewed the change and confirm the stock update."),
                    key=confirm_key,
                )
                confirm_col, cancel_col = st.columns(2)
                with confirm_col:
                    apply_command = st.button(
                        L(":material/check: אשר ועדכן מלאי", ":material/check: Confirm stock update"),
                        key="quick_command_confirm",
                        disabled=not confirmed,
                        type="primary",
                    )
                with cancel_col:
                    cancel_command = st.button(L(":material/close: בטל", ":material/close: Cancel"), key="quick_command_cancel")

            if cancel_command:
                st.session_state[pending_key] = None
                st.session_state[version_key] = version + 1
                st.rerun()
            if apply_command:
                push_backup("stock", f"{L('פקודת מלאי', 'Stock command')}: {pending['command'][:40]}")
                if is_weight:
                    conn.execute(
                        "UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?",
                        (pending["added_base"], pending["sku"]),
                    )
                else:
                    conn.execute(
                        "UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?",
                        (pending["added_base"], pending["sku"]),
                    )
                conn.commit()
                reconcile_batches()
                st.session_state["flash"] = L(
                    f"נוספו {amount_text} למק\"ט {pending['sku']}.",
                    f"Added {amount_text} to SKU {pending['sku']}.",
                )
                st.session_state[pending_key] = None
                st.session_state[version_key] = version + 1
                st.rerun()
