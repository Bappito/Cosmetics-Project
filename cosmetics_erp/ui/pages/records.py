"""Projects, alternative SKUs and shipments (read-only lists; sample rows come from cosmetics_erp/db/records.py)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    conn = ctx.conn
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{L("פרויקטים, מק״טים חלופיים ומשלוחים", "Projects, alternative SKUs & shipments")}</h2></div>', unsafe_allow_html=True)
    projects, alternates, shipments = st.tabs([
        L("פרויקטים", "Projects"),
        L("מקטים חלופיים", "Alternative SKUs"),
        L("משלוחים", "Shipments"),
    ])
    with projects:
        df = pd.read_sql("SELECT code, name, customer, sku, status, start_date, due_date FROM Projects ORDER BY due_date", conn)
        st.dataframe(df, hide_index=True, width="stretch") if not df.empty else st.info(L("אין פרויקטים.", "No projects."))
    with alternates:
        df = pd.read_sql("SELECT sku, alt_sku, description, priority FROM AltSkus ORDER BY sku, priority", conn)
        st.dataframe(df, hide_index=True, width="stretch") if not df.empty else st.info(L("אין מקטים חלופיים.", "No alternative SKUs."))
    with shipments:
        df = pd.read_sql("SELECT shipment_no, customer, carrier, ship_type, sku, qty_units, ship_date, status FROM Shipments ORDER BY ship_date", conn)
        st.dataframe(df, hide_index=True, width="stretch") if not df.empty else st.info(L("אין משלוחים.", "No shipments."))
