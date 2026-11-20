from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    add_batch = ctx.add_batch
    apply_picks = ctx.apply_picks
    conn = ctx.conn
    gen_batch_no = ctx.gen_batch_no
    is_he = ctx.is_he
    log_consumption = ctx.log_consumption
    log_move = ctx.log_move
    plan_fefo = ctx.plan_fefo
    push_backup = ctx.push_backup
    render_where_used_simulator = ctx.render_where_used_simulator
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_prod"]}</h2></div>', unsafe_allow_html=True)
    st.info("**סימולטור קו ייצור:** קבע כמה ק\"ג בלק את/ה מתכנן/ת לייצר ולמתי – המערכת בודקת את **מחסן חומרי הגלם (`RAW`)** ומראה מתי יהיה חוסר.")

    bulk_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'BULK'", conn)
    for _, b_r in bulk_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (b_r["sku"],))
    conn.commit()

    df_sched_prod = pd.read_sql("""
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
        WHERE c.item_type = 'BULK'
    """, conn)

    df_bom_prod = pd.read_sql("""
        SELECT b.component_sku, c.name AS comp_name, b.comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        WHERE p.item_type = 'BULK' AND c.item_type = 'RAW'
        ORDER BY b.component_sku, b.parent_sku
    """, conn)

    render_where_used_simulator(df_sched_prod, df_bom_prod, "ק\"ג בלק" if is_he else "kg Bulk", "prod")

    st.divider()
    st.subheader(L("דיווח ייצור בקו והעברת החומר המוכן למחסן בלקים", "Report Production & Transfer Ready Bulk"))
    if bulk_df.empty:
        st.warning("אין בלקים בקטלוג.")
    else:
        with st.container(border=True):
            st.caption(L(
                "בחר/י מוצר, כמות ואצווה. לפני ביצוע תוצג בדיקת זמינות חומרי גלם לפי FEFO.",
                "Choose the bulk item, quantity, and batch. Available raw-material stock is checked using FEFO before production.",
            ))
            with st.form("production_execute_form"):
                cp1, cp2, cp3, cp4 = st.columns([2.2, 1.2, 1.7, 1.4])
                with cp1:
                    sel_bulk_make = st.selectbox(
                        L("בלק לייצור", "Bulk to produce"),
                        bulk_df["sku"] + " - " + bulk_df["name"],
                        key="production_bulk_sku",
                    )
                sel_b_sku = sel_bulk_make.split(" - ")[0]
                with cp2:
                    kg_to_make = st.number_input(
                        L("כמות לייצור (ק\"ג)", "Production quantity (kg)"),
                        min_value=1.0,
                        value=10.0,
                        step=1.0,
                        key="production_quantity_kg",
                    )
                with cp3:
                    prod_batch_in = st.text_input(
                        L("מספר אצווה (Batch #)", "Batch number"),
                        value=gen_batch_no(sel_b_sku),
                        key=f"prod_bno_{sel_b_sku}",
                    )
                with cp4:
                    prod_exp_in = st.date_input(
                        L("תאריך תפוגה", "Expiry date"),
                        value=date.today() + timedelta(days=180),
                        key="prod_exp",
                    )
                run_production = st.form_submit_button(
                    L(":material/play_arrow: ייצר בלק עכשיו", ":material/play_arrow: Produce bulk"),
                    type="primary",
                    use_container_width=True,
                )

        if run_production:
            b_sku = sel_b_sku
            if prod_exp_in < date.today():
                st.error(L("תאריך התפוגה חייב להיות היום או בעתיד.", "The expiry date must be today or later."))
                st.stop()
            bom_rows = pd.read_sql("SELECT component_sku, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(b_sku,))
            now_d = datetime.now().strftime("%Y-%m-%d")

            plans = []
            errors = []
            for _, br in bom_rows.iterrows():
                need_g = float(br["req_weight_grams"]) * kg_to_make
                picks, short = plan_fefo(br["component_sku"], need_g, True)
                if short > 1e-6:
                    errors.append(f"{br['component_sku']}: חסרים {short/1000:.2f} ק\"ג במלאי תקף (לא פג תוקף)")
                plans.append((br["component_sku"], need_g, picks))

            if errors:
                st.error("לא ניתן לייצר – אין מספיק חומר גלם תקף:\n\n" + "\n\n".join(errors))
            else:
                kg_unit = L('ק"ג', "kg")
                push_backup("stock", f"{L('ייצור בלק', 'Bulk production')} {b_sku} ({kg_to_make:g} {kg_unit})")
                new_batch_no = (prod_batch_in or "").strip() or gen_batch_no(b_sku)

                limiting = None
                for _, _, picks in plans:
                    for p in picks:
                        if p["expiry"] and (limiting is None or p["expiry"] < limiting):
                            limiting = p["expiry"]
                exp_s = prod_exp_in.strftime("%Y-%m-%d")
                capped = False
                if limiting and exp_s > limiting:
                    exp_s = limiting
                    capped = True

                for comp_sku, need_g, picks in plans:
                    apply_picks(picks, True)
                    log_consumption(b_sku, new_batch_no, comp_sku, picks, True, f"PROD {b_sku}")
                    log_move(comp_sku, "WH_RAW", "WH_LINE", need_g, True, f"PROD {b_sku} / {new_batch_no}")
                    conn.execute("""
                        UPDATE Catalog
                        SET weight_grams = MAX(0, weight_grams - ?),
                            stock_movements = ?
                        WHERE sku = ?
                    """, (need_g, f"-{need_g/1000:.2f} ק\"ג לבלק {b_sku}", comp_sku))

                produced_g = kg_to_make * 1000.0
                add_batch(b_sku, new_batch_no, produced_g, True, exp_s, "PRODUCTION")
                log_move(b_sku, "WH_LINE", "WH_BULK", produced_g, True, f"PROD {b_sku} / {new_batch_no}")
                conn.execute("""
                    UPDATE Catalog
                    SET weight_grams = weight_grams + ?,
                        stock_movements = ?,
                        last_stock_entry = ?
                    WHERE sku = ?
                """, (produced_g, f"+{kg_to_make:.1f} ק\"ג מקו ייצור", f"{now_d} (+{kg_to_make:.1f} ק\"ג)", b_sku))
                conn.commit()
                msg = f"יוצרו {kg_to_make} ק\"ג של בלק {b_sku} באצווה {new_batch_no} (תפוגה {exp_s}). חומרי הגלם נגרעו לפי FEFO והבלק הועבר למחסן בלקים."
                if capped:
                    msg += f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של חומר הגלם ({limiting})."
                st.session_state["flash"] = msg
                st.rerun()
