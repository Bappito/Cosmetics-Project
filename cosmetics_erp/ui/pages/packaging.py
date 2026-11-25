from __future__ import annotations

import pandas as pd
import streamlit as st
from datetime import date, datetime, timedelta

from cosmetics_erp.services.manufacturing import plan_components, post_run
from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    UI = ctx.UI
    conn = ctx.conn
    svc = ctx.inventory_service
    gen_batch_no = ctx.gen_batch_no
    is_he = ctx.is_he
    push_backup = ctx.push_backup
    render_where_used_simulator = ctx.render_where_used_simulator
    u_label = ctx.u_label
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_pack"]}</h2></div>', unsafe_allow_html=True)
    st.info(L("**סימולטור אריזה משולב:** קבע כמה יחידות מוצר סופי את/ה מתכנן/ת לארוז ולמתי – המערכת בודקת במקביל את **החומר המוכן ממחסן הבלקים (`BULK`)** ואת **האריזות ממחסן האריזות (`PKG`)**.", "**Packaging simulator:** set how many finished units to pack and when – the system checks the **bulk warehouse (`BULK`)** and the **packaging warehouse (`PKG`)** together."))

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
        st.warning(L("אין מוצרים סופיים בקטלוג.", "No finished products in the catalog."))
    else:
        with st.container(border=True):
            st.caption(L(
                "בחר/י מוצר וכמות. לפני האריזה נבדקת זמינות הבלק ורכיבי האריזה לפי FEFO.",
                "Choose a finished product and quantity. Bulk and packaging availability is checked using FEFO before packing.",
            ))
            with st.form("packaging_execute_form"):
                ck1, ck2, ck3, ck4 = st.columns([2.2, 1.2, 1.7, 1.4])
                with ck1:
                    sel_fg_pack = st.selectbox(
                        L("מוצר סופי לאריזה", "Finished product to pack"),
                        fg_df["sku"] + " - " + fg_df["name"],
                        key="packaging_finished_sku",
                    )
                sel_f_sku = sel_fg_pack.split(" - ")[0]
                with ck2:
                    units_to_pack = st.number_input(
                        L("כמות לאריזה (יחידות)", "Packing quantity (units)"),
                        min_value=1,
                        value=100,
                        step=10,
                        key="packaging_quantity_units",
                    )
                with ck3:
                    pack_batch_in = st.text_input(
                        L("מספר אצווה (Batch #)", "Batch number"),
                        value=gen_batch_no(sel_f_sku),
                        key=f"pack_bno_{sel_f_sku}",
                    )
                with ck4:
                    pack_exp_in = st.date_input(
                        L("תאריך תפוגה", "Expiry date"),
                        value=date.today() + timedelta(days=730),
                        key="pack_exp",
                    )
                run_packaging = st.form_submit_button(
                    L(":material/check_circle: בצע אריזה", ":material/check_circle: Pack product"),
                    type="primary",
                    width="stretch",
                )

        if run_packaging:
            f_sku = sel_f_sku
            if pack_exp_in < date.today():
                st.error(L("תאריך התפוגה חייב להיות היום או בעתיד.", "The expiry date must be today or later."))
                st.stop()
            bom_p = pd.read_sql("SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(f_sku,))
            now_d = datetime.now().strftime("%Y-%m-%d")
            components = []
            for _, br in bom_p.iterrows():
                is_w_c = br["comp_type"] == "BULK"
                components.append({
                    "sku": br["component_sku"],
                    "need": float(br["req_weight_grams"] if is_w_c else br["req_qty_units"]) * units_to_pack,
                    "is_weight": is_w_c,
                    "from_wh": "WH_BULK" if is_w_c else "WH_PACK",
                })
            plans, shortages = plan_components(svc, components)
            errors = []
            for sh in shortages:
                short_txt = f"{sh['short'] / 1000:.2f} ק\"ג" if sh["is_weight"] else f"{sh['short']:.0f} יח'"
                errors.append(f"{sh['sku']}: " + L(f"חסרים {short_txt} במלאי תקף (לא פג תוקף)", f"short {short_txt} of valid stock (not expired)"))
            requested_batch = (pack_batch_in or "").strip() or gen_batch_no(f_sku)
            if ctx.batch_exists(f_sku, requested_batch):
                errors.append(L(
                    f"אצווה {requested_batch} כבר קיימת למוצר {f_sku}. בחר/י מספר אצווה אחר.",
                    f"Batch {requested_batch} already exists for product {f_sku}. Choose another batch number.",
                ))

            if errors:
                st.error(L("לא ניתן לבצע אריזה – אין מספיק רכיבים תקפים:", "Cannot pack – not enough valid components:") + "\n\n" + "\n\n".join(errors))
            else:
                push_backup("stock", f"{L('אריזת', 'Packing')} {f_sku} ({units_to_pack} {u_label})")
                result = post_run(
                    conn, svc, kind="packaging", parent_sku=f_sku, batch_no=requested_batch, plans=plans,
                    expiry=pack_exp_in.strftime("%Y-%m-%d"), output_amount=float(units_to_pack),
                    output_is_weight=False, now_d=now_d,
                )
                msg = f"נארזו {units_to_pack} יח' של {f_sku} באצווה {requested_batch} (תפוגה {result['expiry']}). המלאי נגרע ממחסן הבלקים וממחסן האריזות לפי FEFO."
                if result["capped"]:
                    msg += f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של הרכיבים ({result['limiting']})."
                st.session_state["flash"] = msg
                st.rerun()
