from __future__ import annotations

import pandas as pd
import streamlit as st

from cosmetics_erp.ui.context import PageContext


def render(ctx: PageContext) -> None:
    L = ctx.L
    PLAN_PERIODS = ctx.PLAN_PERIODS
    UI = ctx.UI
    conn = ctx.conn
    fmt_val = ctx.fmt_val
    get_incoming_map = ctx.get_incoming_map
    is_he = ctx.is_he
    render_quick_planner = ctx.render_quick_planner
    u_label = ctx.u_label
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_work"]}</h2></div>', unsafe_allow_html=True)
    st.info(
        "**סימולטור עבודה מסכם לפי חודשים ושבועות:** מציג לכל **מק\"ט אב** כמה יחידות **מתוכנן** לייצר בכל שבוע, כמה יחידות **אפשר להכין בפועל** (משילוב חו\"ג + בלקים + אריזות + הגעות PO), ומתי יווצר חוסר. **לחץ על כל תא שבועי** כדי לפתוח בועה צפה מעליו עם פירוט מה חסר וכמה!"
    )

    fg_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'FG'", conn)
    for _, f_r in fg_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (f_r["sku"],))
    conn.commit()

    df_sched_work = pd.read_sql("""
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
        WHERE c.item_type = 'FG'
    """, conn)

    render_quick_planner(df_sched_work, u_label, "work_master")

    cat_all = pd.read_sql("SELECT * FROM Catalog", conn).set_index("sku")
    bom_all = pd.read_sql("SELECT * FROM BOM", conn)
    incoming_w = get_incoming_map()

    week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    month1_name = PLAN_PERIODS[0][1]
    month2_name = PLAN_PERIODS[4][1]

    rem_pkg = {sku: float(r["qty_units"]) for sku, r in cat_all[cat_all["item_type"] == "PKG"].iterrows()}
    rem_bulk_g = {sku: float(r["weight_grams"]) for sku, r in cat_all[cat_all["item_type"] == "BULK"].iterrows()}
    rem_raw_g = {sku: float(r["weight_grams"]) for sku, r in cat_all[cat_all["item_type"] == "RAW"].iterrows()}

    work_sim_cells = {}

    for w_col in week_cols:
        arrivals_this_week = {}
        for stock_dict in (rem_pkg, rem_bulk_g, rem_raw_g):
            for s_key in list(stock_dict.keys()):
                ent = incoming_w.get((s_key, w_col))
                if ent:
                    stock_dict[s_key] += ent["amt"]
                    arrivals_this_week[s_key] = ent

        for _, fg_row in df_sched_work.iterrows():
            f_sku = fg_row["sku"]
            planned_u = int(fg_row[w_col])
            sub_bom = bom_all[bom_all["parent_sku"] == f_sku]

            shortages_list = []
            max_makeable_this_week = planned_u

            rel_skus = []
            for _, br0 in sub_bom.iterrows():
                rel_skus.append(br0["component_sku"])
                if br0["comp_type"] == "BULK":
                    for _, rb0 in bom_all[bom_all["parent_sku"] == br0["component_sku"]].iterrows():
                        rel_skus.append(rb0["component_sku"])
            arr_lines = []
            for s_key in dict.fromkeys(rel_skus):
                ent = arrivals_this_week.get(s_key)
                if ent and s_key in cat_all.index:
                    is_w_s = cat_all.loc[s_key]["item_type"] in ("RAW", "BULK")
                    nm_s = cat_all.loc[s_key]["name"]
                    amt_s = fmt_val(ent["amt"], is_w_s)
                    pos_s = ", ".join(ent["pos"])
                    arr_lines.append(f"+PO {s_key} ({nm_s}): <b>+{amt_s}</b> ({pos_s})")

            for _, br in sub_bom.iterrows():
                c_sku = br["component_sku"]
                if c_sku not in cat_all.index:
                    continue
                c_name = cat_all.loc[c_sku]["name"]

                if br["comp_type"] == "PKG":
                    req_u_per_fg = float(br["req_qty_units"])
                    req_u_total = planned_u * req_u_per_fg
                    avail_u = rem_pkg.get(c_sku, 0.0)

                    can_by_this_pkg = int(max(0.0, avail_u) // req_u_per_fg) if req_u_per_fg > 0 else planned_u
                    max_makeable_this_week = min(max_makeable_this_week, can_by_this_pkg)

                    after_u = avail_u - req_u_total
                    rem_pkg[c_sku] = after_u
                    if after_u < -1e-6:
                        shortages_list.append(f"אריזה {c_sku} ({c_name}): <b style='color:#f87171 !important;'>{fmt_val(after_u, False)}</b>")

                elif br["comp_type"] == "BULK":
                    req_g_per_fg = float(br["req_weight_grams"])
                    req_g_total = planned_u * req_g_per_fg
                    avail_b_g = rem_bulk_g.get(c_sku, 0.0)

                    if avail_b_g >= req_g_total - 1e-6:
                        rem_bulk_g[c_sku] = avail_b_g - req_g_total
                    else:
                        used_from_existing_bulk = max(0.0, avail_b_g)
                        needed_extra_bulk_g = req_g_total - used_from_existing_bulk
                        needed_extra_bulk_kg = needed_extra_bulk_g / 1000.0

                        raw_bom = bom_all[bom_all["parent_sku"] == c_sku]
                        max_cookable_bulk_kg = needed_extra_bulk_kg
                        raw_missing_for_bulk = []

                        for _, rb in raw_bom.iterrows():
                            r_sku = rb["component_sku"]
                            if r_sku not in cat_all.index:
                                continue
                            r_name = cat_all.loc[r_sku]["name"]
                            req_raw_g_per_kg = float(rb["req_weight_grams"])
                            req_raw_total_g = needed_extra_bulk_kg * req_raw_g_per_kg
                            avail_r_g = rem_raw_g.get(r_sku, 0.0)

                            can_kg_by_raw = (max(0.0, avail_r_g) / req_raw_g_per_kg) if req_raw_g_per_kg > 0 else needed_extra_bulk_kg
                            max_cookable_bulk_kg = min(max_cookable_bulk_kg, can_kg_by_raw)

                            after_r_g = avail_r_g - req_raw_total_g
                            rem_raw_g[r_sku] = after_r_g
                            if after_r_g < -1e-6:
                                raw_missing_for_bulk.append(f"חו\"ג {r_sku} ({r_name}): <b style='color:#f87171 !important;'>{fmt_val(after_r_g, True)}</b>")

                        total_usable_bulk_g = used_from_existing_bulk + (max_cookable_bulk_kg * 1000.0)
                        can_by_bulk_and_raw = int(total_usable_bulk_g // req_g_per_fg) if req_g_per_fg > 0 else planned_u
                        max_makeable_this_week = min(max_makeable_this_week, can_by_bulk_and_raw)

                        after_b_g = avail_b_g - req_g_total
                        rem_bulk_g[c_sku] = after_b_g
                        shortages_list.append(f"בלק {c_sku} ({c_name}): <b style='color:#f87171 !important;'>{fmt_val(after_b_g, True)}</b>")
                        shortages_list.extend(raw_missing_for_bulk)

            is_week_ok = (len(shortages_list) == 0)
            missing_fg_units = max(0, planned_u - max_makeable_this_week)

            work_sim_cells[(f_sku, w_col)] = {
                "planned": planned_u,
                "makeable": max_makeable_this_week,
                "missing_fg": missing_fg_units,
                "is_ok": is_week_ok,
                "shortages": shortages_list,
                "arrivals": arr_lines
            }

    st.subheader(L("טבלת סימולטור עבודה לפי מק\"ט אב, חודשים ושבועות (לחץ על כל תא לפתיחת בועה מעליו)", "Master Work Schedule & Shortages by Parent SKU"))

    legend_w = (
        f"<div class='legend-box'>"
        f"<span class='legend-pill-ok'>{'ירוק = ניתן להכין את כל הכמות המתוכננת לשבוע זה' if is_he else 'Green = All Planned Units Can Be Made'}</span>"
        f"<span class='legend-pill-short'>{'אדום = חוסר בשבוע זה (לחץ על התא לפתיחת בועת פירוט מעליו)' if is_he else 'Red = Shortage in Week (Click to open bubble above)'}</span>"
        f"</div>"
    )
    st.markdown(legend_w, unsafe_allow_html=True)

    arr_title = L("הגעות רכש השבוע:", "PO arrivals this week:")
    close_hint_txt = L("לחץ שוב על התא לסגירת הבועה", "Click cell again to close")
    rows_work_html = ""
    for _, fg_row in df_sched_work.iterrows():
        f_sku = fg_row["sku"]
        f_label = fg_row["parent_label"]
        tot_planned_all = 0
        tot_makeable_all = 0

        week_tds = ""
        for w_idx, w_col in enumerate(week_cols):
            c_data = work_sim_cells[(f_sku, w_col)]
            p_u = c_data["planned"]
            m_u = c_data["makeable"]
            miss_u = c_data["missing_fg"]
            tot_planned_all += p_u
            tot_makeable_all += m_u
            wk_title = PLAN_PERIODS[w_idx][2]

            arr_lines_c = c_data["arrivals"]
            arr_badge = f"<span class='cell-sub-plan'>+PO ({len(arr_lines_c)})</span>" if arr_lines_c else ""
            arr_block = (
                f"<hr style='margin:5px 0; border-color:rgba(255,255,255,0.22);'><b style='color:#38bdf8 !important;'>{arr_title}</b><br>" + "<br>".join(arr_lines_c)
                if arr_lines_c else ""
            )

            if c_data["is_ok"]:
                td_cls = "stock-ok"
                top_txt = f"{'אפשרי' if is_he else 'Can Make'}: {m_u:,} {u_label}"
                sub_txt = f"<span class='cell-sub-plan'>{'מתוכנן' if is_he else 'Planned'}: {p_u:,} {u_label}</span>{arr_badge}"
                details_body = (
                    f"<div class='cell-breakdown-fit'>"
                    f"<div style='font-weight:800; color:#38bdf8 !important; margin-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.22); padding-bottom:4px;'>{f_sku} | {wk_title}</div>"
                    f"<div>מתוכנן לשבוע: <b>{p_u:,} {u_label}</b></div>"
                    f"<div>ניתן להכין: <b>{m_u:,} {u_label}</b></div>"
                    f"<div style='color:#4ade80 !important; font-weight:800;'>אין חוסרים בשבוע זה!</div>"
                    f"{arr_block}"
                    f"<span class='bubble-close-hint'>{close_hint_txt}</span>"
                    f"</div>"
                )
            else:
                td_cls = "stock-short"
                top_txt = f"{'אפשרי' if is_he else 'Can Make'}: {m_u:,} / {p_u:,} {u_label}"
                sub_txt = f"<span class='cell-sub-plan' style='color:#ef4444; font-weight:800;'>{'חסר למוצר' if is_he else 'Short'}: <span dir='ltr'>-{miss_u:,}</span> {u_label}</span>{arr_badge}"
                short_items_html = "<br>".join(c_data["shortages"])
                details_body = (
                    f"<div class='cell-breakdown-fit'>"
                    f"<div style='font-weight:800; color:#f87171 !important; margin-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.22); padding-bottom:4px;'>{f_sku} | {wk_title}</div>"
                    f"<div>מתוכנן: <b>{p_u:,} {u_label}</b> | ניתן להכין: <b>{m_u:,} {u_label}</b></div>"
                    f"<hr style='margin:5px 0; border-color:rgba(255,255,255,0.22);'>"
                    f"<b style='color:#38bdf8 !important;'>{'מה חסר וכמה (מצטבר):' if is_he else 'Missing Components:'}</b><br>"
                    f"{short_items_html}"
                    f"{arr_block}"
                    f"<span class='bubble-close-hint'>{close_hint_txt}</span>"
                    f"</div>"
                )

            week_tds += (
                f"<td class='{td_cls}'>"
                f"<details class='cell-details'>"
                f"<summary><span class='cell-main-val'>{top_txt}</span>{sub_txt}</summary>"
                f"{details_body}"
                f"</details>"
                f"</td>"
            )

        tot_diff = tot_makeable_all - tot_planned_all
        sum_cls = "summary-ok" if tot_diff >= 0 else "summary-short"
        sum_txt = (
            f"אפשרי: {tot_makeable_all:,}<br><span style='font-size:0.78rem;'>מתוך {tot_planned_all:,} {u_label}</span>"
            if is_he else
            f"Can Make: {tot_makeable_all:,}<br><span style='font-size:0.78rem;'>of {tot_planned_all:,} {u_label}</span>"
        )

        rows_work_html += (
            f"<tr class='group-end'>"
            f"<td class='parent-col' style='font-size:0.95rem;'>{f_label}</td>"
            f"{week_tds}"
            f"<td class='{sum_cls}'>{sum_txt}</td>"
            f"</tr>"
        )

    work_parent_heading = "מק\"ט אב ושם מוצר" if is_he else "Parent SKU & Name"
    work_total_heading = "סה\"כ תקופתי (אפשרי מול מתוכנן)" if is_he else "Total Makeable vs Planned"
    work_matrix_html = (
        f"<div class='table-responsive'><table class='matrix-table'>"
        f"<caption class='sr-only'>{L('יכולת ייצור מול תוכנית שבועית', 'Weekly production feasibility versus plan')}</caption>"
        f"<thead>"
        f"<tr>"
        f"<th scope='col' rowspan='2' style='width:16%;'>{work_parent_heading}</th>"
        f"<th scope='colgroup' colspan='4' style='width:37%;'>{month1_name}</th>"
        f"<th scope='colgroup' colspan='4' style='width:37%;'>{month2_name}</th>"
        f"<th scope='col' rowspan='2' style='width:10%;'>{work_total_heading}</th>"
        f"</tr><tr>"
        f"<th scope='col'>{PLAN_PERIODS[0][2]}</th><th scope='col'>{PLAN_PERIODS[1][2]}</th><th scope='col'>{PLAN_PERIODS[2][2]}</th><th scope='col'>{PLAN_PERIODS[3][2]}</th>"
        f"<th scope='col'>{PLAN_PERIODS[4][2]}</th><th scope='col'>{PLAN_PERIODS[5][2]}</th><th scope='col'>{PLAN_PERIODS[6][2]}</th><th scope='col'>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead><tbody>{rows_work_html}</tbody></table></div>"
    )
    st.markdown(work_matrix_html, unsafe_allow_html=True)
