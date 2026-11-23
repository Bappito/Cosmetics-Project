from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn

    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_audit"]}</h2></div>', unsafe_allow_html=True)
    st.caption(L(
        "כל שינוי במלאי, בעצי המוצר ובתכנון נרשם כאן, כולל ביטולים. היומן לא נמחק אוטומטית.",
        "Every change to stock, product trees and planning is recorded here, including undos. The log is never trimmed automatically.",
    ))
    rows = pd.read_sql("SELECT at, scope, action FROM AuditLog ORDER BY audit_id DESC LIMIT 300", conn)
    if rows.empty:
        st.info(L("אין עדיין שינויים ביומן.", "No changes logged yet."))
        return
    view = pd.DataFrame({
        L("זמן", "Time"): rows["at"],
        L("אזור", "Area"): rows["scope"].map({"stock": L("מלאי ועצים", "Stock & trees"), "schedule": L("תכנון", "Planning")}).fillna(rows["scope"]),
        L("פעולה", "Action"): rows["action"],
    })
    st.dataframe(view, width="stretch", hide_index=True, column_order=list(view.columns))
