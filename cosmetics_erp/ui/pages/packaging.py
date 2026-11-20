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
    u_label = ctx.u_label
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_pack"]}</h2></div>', unsafe_allow_html=True)
    st.info("**סימולטור אריזה משולב:** קבע כמה יחידות מוצר סופי את/ה מתכנן/ת לארוז ולמתי – המערכת בודקת במקביל את **החומר המוכן ממחסן הבלקים (`BULK`)** ואת **האריזות ממחסן האריזות (`PKG`)**.")

    fg_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'FG'", conn)
    for _, f_r in fg_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (f_r["sku"],))
    conn.commit()

    df_sched_pack = pd.read_sql("""
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
        WHERE c.item_type = 'FG'
    """, conn)

    df_bom_pack = pd.read_sql("""
        SELECT b.component_sku, c.name AS comp_name, c.item_type AS comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        WHERE p.item_type = 'FG' AND c.item_type IN ('BULK', 'PKG')
        ORDER BY CASE WHEN c.item_type = 'BULK' THEN 0 ELSE 1 END, b.component_sku, b.parent_sku
    """, conn)

    view_mode_pack = st.radio(
        "תצוגת רכיבים בסימולטור האריזה:" if is_he else "Show in Packaging Simulator:",
        [
            "הכל יחד (חומר מבלקים + אריזות)" if is_he else "All Combined (Bulks + Packaging)",
            "רק חומר ממחסן בלקים" if is_he else "Only Bulks",
            "רק אריזות (בקבוקים/מכסים/מתזים/מדבקות)" if is_he else "Only Packaging"
        ],
        horizontal=True
    )
    if "רק חומר" in view_mode_pack or "Only Bulks" in view_mode_pack:
        df_bom_pack = df_bom_pack[df_bom_pack["comp_type"] == "BULK"]
    elif "רק אריזות" in view_mode_pack or "Only Packaging" in view_mode_pack:
        df_bom_pack = df_bom_pack[df_bom_pack["comp_type"] == "PKG"]

    render_where_used_simulator(df_sched_pack, df_bom_pack, u_label, "pack")

    st.divider()
    st.subheader(L("ביצוע פעולת מילוי ואריזה (גריעה ממחסן בלקים וממחסן אריזות)", "Execute Filling & Packaging"))
    if fg_df.empty:
        st.warning("אין מוצרים סופיים בקטלוג.")
    else:
        ck1, ck2, ck3, ck4 = st.columns([2.2, 1.2, 1.7, 1.4])
        with ck1:
            sel_fg_pack = st.selectbox("בחר מוצר סופי לאריזה:", fg_df["sku"] + " - " + fg_df["name"])
        sel_f_sku = sel_fg_pack.split(" - ")[0]
        with ck2:
            units_to_pack = st.number_input("כמות יחידות למילוי ואריזה:", min_value=1, value=100, step=10)
        with ck3:
            pack_batch_in = st.text_input("מספר אצווה (Batch #) למוצר:", value=gen_batch_no(sel_f_sku), key=f"pack_bno_{sel_f_sku}")
        with ck4:
            pack_exp_in = st.date_input("תאריך תפוגה למוצר:", value=date.today() + timedelta(days=730), key="pack_exp")

        if st.button(":material/check_circle: בצע אריזה (גרע בלק ממחסן בלקים + בקבוקים/מכסים/מדבקות ממחסן אריזות)"):
            f_sku = sel_f_sku
            bom_p = pd.read_sql("SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(f_sku,))
            now_d = datetime.now().strftime("%Y-%m-%d")

            plans = []
            errors = []
            for _, br in bom_p.iterrows():
                is_w_c = (br["comp_type"] == "BULK")
                need = float(br["req_weight_grams"] if is_w_c else br["req_qty_units"]) * units_to_pack
                picks, short = plan_fefo(br["component_sku"], need, is_w_c)
                if short > 1e-6:
                    short_txt = f"{short/1000:.2f} ק\"ג" if is_w_c else f"{short:.0f} יח'"
                    errors.append(f"{br['component_sku']}: חסרים {short_txt} במלאי תקף (לא פג תוקף)")
                plans.append((br["component_sku"], is_w_c, need, picks))

            if errors:
                st.error("לא ניתן לבצע אריזה – אין מספיק רכיבים תקפים:\n\n" + "\n\n".join(errors))
            else:
                push_backup("stock", f"{L('אריזת', 'Packing')} {f_sku} ({units_to_pack} {u_label})")
                new_batch_no = (pack_batch_in or "").strip() or gen_batch_no(f_sku)

                limiting = None
                for _, _, _, picks in plans:
                    for p in picks:
                        if p["expiry"] and (limiting is None or p["expiry"] < limiting):
                            limiting = p["expiry"]
                exp_s = pack_exp_in.strftime("%Y-%m-%d")
                capped = False
                if limiting and exp_s > limiting:
                    exp_s = limiting
                    capped = True

                for comp_sku, is_w_c, need, picks in plans:
                    apply_picks(picks, is_w_c)
                    log_consumption(f_sku, new_batch_no, comp_sku, picks, is_w_c, f"PACK {f_sku}")
                    log_move(comp_sku, "WH_BULK" if is_w_c else "WH_PACK", "WH_LINE", need, is_w_c, f"PACK {f_sku} / {new_batch_no}")
                    if is_w_c:
                        conn.execute("UPDATE Catalog SET weight_grams = MAX(0, weight_grams - ?), stock_movements = ? WHERE sku = ?",
                                     (need, f"-{need/1000:.2f} ק\"ג לאריזת {f_sku}", comp_sku))
                    else:
                        conn.execute("UPDATE Catalog SET qty_units = MAX(0, qty_units - ?), stock_movements = ? WHERE sku = ?",
                                     (need, f"-{need:.0f} יח' לאריזת {f_sku}", comp_sku))

                add_batch(f_sku, new_batch_no, float(units_to_pack), False, exp_s, "PACKING")
                log_move(f_sku, "WH_LINE", "WH_FG", float(units_to_pack), False, f"PACK {f_sku} / {new_batch_no}")
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku = ?",
                             (units_to_pack, f"{now_d} (+{units_to_pack} יח')", f_sku))
                conn.commit()
                msg = f"נארזו {units_to_pack} יח' של {f_sku} באצווה {new_batch_no} (תפוגה {exp_s}). המלאי נגרע ממחסן הבלקים וממחסן האריזות לפי FEFO."
                if capped:
                    msg += f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של הרכיבים ({limiting})."
                st.session_state["flash"] = msg
                st.rerun()
