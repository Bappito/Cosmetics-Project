from __future__ import annotations

import pandas as pd
import streamlit as st
import re

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    push_backup = ctx.push_backup
    reconcile_batches = ctx.reconcile_batches
    render_undo_button = ctx.render_undo_button
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_ai"]}</h2></div>', unsafe_allow_html=True)
    st.caption("כתוב פקודה כגון: `תוסיף 5 קילו ל-1001` או `תוסיף 10 קילו ל-2001` או `תוסיף 300 יחידות ל-3001`")
    render_undo_button("stock", "undo_agent")
    cmd_in = st.chat_input("כתוב פקודה לביצוע מיידי...")
    if cmd_in:
        nums = re.findall(r"(\d+(?:\.\d+)?)", cmd_in)
        if len(nums) >= 2:
            s_code = nums[-1]
            val = float(nums[0])
            exists = conn.execute("SELECT item_type FROM Catalog WHERE sku=?", (s_code,)).fetchone()
            if not exists:
                st.error(f"מק\"ט {s_code} לא קיים בקטלוג.")
            else:
                push_backup("stock", f"{L('פקודת סוכן', 'Agent command')}: {cmd_in[:40]}")
                if "קילו" in cmd_in or "kg" in cmd_in.lower():
                    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?", (val * 1000.0, s_code))
                    conn.commit()
                    msg_a = f"נוספו {val} ק\"ג למק\"ט {s_code}!"
                else:
                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?", (val, s_code))
                    conn.commit()
                    msg_a = f"נוספו {val} יח' למק\"ט {s_code}!"
                reconcile_batches()
                st.success(msg_a)
