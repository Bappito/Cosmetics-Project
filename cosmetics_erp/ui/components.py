from __future__ import annotations

import sqlite3
from typing import Any, Callable, Sequence

import streamlit as st


class UIComponents:
    def __init__(
        self,
        *,
        translate: Callable[[str, str], str],
        is_he: bool,
        unit_label: str,
        plan_periods: Sequence[tuple[str, str, str]],
        conn: sqlite3.Connection,
        push_backup: Callable[..., Any],
        last_backup: Callable[..., Any],
        undo_backup: Callable[..., Any],
        get_incoming_map: Callable[..., Any],
        format_value: Callable[..., str],
    ) -> None:
        self.translate = translate
        self.is_he = is_he
        self.u_label = unit_label
        self.plan_periods = plan_periods
        self.conn = conn
        self.push_backup = push_backup
        self.last_backup = last_backup
        self.undo_backup = undo_backup
        self.get_incoming_map = get_incoming_map
        self.format_value = format_value

    def render_undo_button(self, scope, key):
        info = self.last_backup(scope)
        if info:
            lbl = self.translate(f":material/undo: בטל פעולה אחרונה: {info[1]} ({info[2][5:16]})", f":material/undo: Undo last: {info[1]} ({info[2][5:16]})")
            if st.button(lbl, key=key):
                done = self.undo_backup(scope)
                st.session_state["flash"] = self.translate(f"שוחזר המצב שלפני: {done}", f"Restored the state before: {done}")
                st.rerun()
        else:
            st.caption(self.translate("אין גיבוי זמין לשחזור", "No backup available to restore"))

    def render_quick_planner(self, df_sched_sub, unit_name, key_prefix):
        st.markdown("<div class='plan-box'>", unsafe_allow_html=True)
        st.markdown(
            f"**{self.translate('תכנון ייצור: קבע כמה את/ה מתכנן/ת לייצר ולמתי (חודש ושבוע)', 'Production Planner: Set Planned Quantity & Target Week')}**"
        )
        period_labels = [f"{p[0]} | {p[1]} - {p[2]}" for p in self.plan_periods]
        c_p1, c_p2, c_p3, c_p4 = st.columns([2.2, 2.2, 1.5, 1.5])
        with c_p1:
            sel_parent_plan = st.selectbox(
                "בחר מק\"ט אב לתכנון:" if self.is_he else "Select Parent SKU:",
                df_sched_sub["parent_label"],
                key=f"{key_prefix}_plan_sku"
            )
        with c_p2:
            sel_week_plan = st.selectbox(
                "למתי (בחר חודש ושבוע):" if self.is_he else "When (Month & Week):",
                period_labels,
                key=f"{key_prefix}_plan_wk"
            )
        w_code_selected = sel_week_plan.split(" | ")[0]
        p_sku_selected = sel_parent_plan.split(" - ")[0]
        curr_planned_val = float(df_sched_sub[df_sched_sub["sku"] == p_sku_selected][w_code_selected].iloc[0])

        with c_p3:
            new_planned_qty = st.number_input(
                f"{'כמות מתוכננת' if self.is_he else 'Planned Qty'} ({unit_name}):",
                min_value=0.0, value=curr_planned_val, step=10.0 if unit_name == self.u_label else 1.0,
                key=f"{key_prefix}_plan_qty"
            )
        with c_p4:
            st.write("")
            if st.button(":material/event_available: עדכן תכנון" if self.is_he else ":material/event_available: Update Plan", key=f"{key_prefix}_plan_btn", use_container_width=True):
                self.push_backup("schedule", f"{self.translate('תכנון', 'Plan')} {p_sku_selected} {w_code_selected}")
                self.conn.execute(f"UPDATE WeeklySchedule SET {w_code_selected} = ? WHERE parent_sku = ?", (new_planned_qty, p_sku_selected))
                self.conn.commit()
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    def render_where_used_simulator(self, df_sched_sub, df_bom_sub, parent_unit_str, sim_key_prefix):
        week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
        month1_name = self.plan_periods[0][1]
        month2_name = self.plan_periods[4][1]

        self.render_quick_planner(df_sched_sub, parent_unit_str, sim_key_prefix)
        st.caption(self.translate(
            "לחץ על כל תא בטבלה כדי לפתוח בועה צפה מעליו עם פירוט המלאי והשימוש באותו שבוע.",
            "Click any cell to open a floating bubble above it with the weekly breakdown."
        ))

        incoming = self.get_incoming_map()

        running_balance = {}
        for _, r in df_bom_sub.iterrows():
            c_sku = r["component_sku"]
            if c_sku not in running_balance:
                is_w = (r["comp_type"] in ["RAW", "BULK"])
                running_balance[c_sku] = float(r["avail_grams"] if is_w else r["avail_units"])

        cell_status = {}
        comp_weekly_total_used = {}
        for w_col in week_cols:
            for c_sku, grp in df_bom_sub.groupby("component_sku", sort=False):
                tot_w = 0.0
                for _, r in grp.iterrows():
                    is_w = (r["comp_type"] in ["RAW", "BULK"])
                    factor = float(r["req_weight_grams"] if is_w else r["req_qty_units"])
                    tot_w += float(r[w_col]) * factor
                comp_weekly_total_used[(c_sku, w_col)] = tot_w

        for w_col in week_cols:
            arrivals_now = {}
            for c_sku in list(running_balance.keys()):
                ent = incoming.get((c_sku, w_col))
                if ent:
                    running_balance[c_sku] += ent["amt"]
                    arrivals_now[c_sku] = ent

            for row_idx, r in df_bom_sub.iterrows():
                c_sku = r["component_sku"]
                is_w = (r["comp_type"] in ["RAW", "BULK"])
                per_unit_factor = float(r["req_weight_grams"] if is_w else r["req_qty_units"])
                used_by_this_parent = float(r[w_col]) * per_unit_factor
                tot_used_by_all_parents = comp_weekly_total_used[(c_sku, w_col)]

                before_bal = running_balance.get(c_sku, 0.0)
                after_bal = before_bal - used_by_this_parent
                running_balance[c_sku] = after_bal

                is_ok = (after_bal >= -1e-6)
                cell_status[(row_idx, w_col)] = {
                    "is_ok": is_ok,
                    "before_bal": before_bal,
                    "used_parent": used_by_this_parent,
                    "tot_used_all_parents": tot_used_by_all_parents,
                    "after_bal": after_bal,
                    "incoming": arrivals_now.get(c_sku)
                }

        final_comp_balance = {}
        for c_sku, grp in df_bom_sub.groupby("component_sku", sort=False):
            last_row_idx = grp.index[-1]
            final_comp_balance[c_sku] = cell_status[(last_row_idx, "W8")]

        all_lbl = "הכל" if self.is_he else "All"
        child_opts = [all_lbl] + list((df_bom_sub["component_sku"] + " - " + df_bom_sub["comp_name"]).unique())
        parent_opts = [all_lbl] + list((df_sched_sub["sku"] + " - " + df_sched_sub["parent_name"]).unique())

        s1, s2, s3 = st.columns([2, 1.5, 1.5])
        with s1:
            q_search = st.text_input("חיפוש לפי מק\"ט בן או מק\"ט אב:" if self.is_he else "Search Child or Parent SKU:", key=f"{sim_key_prefix}_q")
        with s2:
            sel_c = st.selectbox("סנן לפי מק\"ט בן:" if self.is_he else "Filter Child SKU:", child_opts, key=f"{sim_key_prefix}_c")
        with s3:
            sel_p = st.selectbox("סנן לפי מק\"ט אב משויך:" if self.is_he else "Filter Linked Parent:", parent_opts, key=f"{sim_key_prefix}_p")

        df_bom_view = df_bom_sub.copy()
        if sel_c != all_lbl:
            df_bom_view = df_bom_view[df_bom_view["component_sku"] == sel_c.split(" - ")[0]]
        if sel_p != all_lbl:
            df_bom_view = df_bom_view[df_bom_view["parent_sku"] == sel_p.split(" - ")[0]]
        if q_search.strip():
            q = q_search.strip()
            df_bom_view = df_bom_view[
                df_bom_view["component_sku"].str.contains(q, case=False, na=False) |
                df_bom_view["comp_name"].str.contains(q, case=False, na=False) |
                df_bom_view["parent_sku"].str.contains(q, case=False, na=False) |
                df_bom_view["parent_name"].str.contains(q, case=False, na=False)
            ]

        rows_sched_html = ""
        for _, row in df_sched_sub.iterrows():
            tot_p = int(row["W1"] + row["W2"] + row["W3"] + row["W4"] + row["W5"] + row["W6"] + row["W7"] + row["W8"])
            rows_sched_html += (
                f"<tr>"
                f"<td class='parent-col'>{row['parent_label']}</td>"
                f"<td><b>{int(row['W1'])}</b> {parent_unit_str}</td><td><b>{int(row['W2'])}</b> {parent_unit_str}</td>"
                f"<td><b>{int(row['W3'])}</b> {parent_unit_str}</td><td><b>{int(row['W4'])}</b> {parent_unit_str}</td>"
                f"<td><b>{int(row['W5'])}</b> {parent_unit_str}</td><td><b>{int(row['W6'])}</b> {parent_unit_str}</td>"
                f"<td><b>{int(row['W7'])}</b> {parent_unit_str}</td><td><b>{int(row['W8'])}</b> {parent_unit_str}</td>"
                f"<td><b>{tot_p:,} {parent_unit_str}</b></td>"
                f"</tr>"
            )

        schedule_parent_heading = "מק\"ט אב ותוכנית ייצור מתוכננת" if self.is_he else "Parent SKU Planned Schedule"
        schedule_total_heading = "סה\"כ מתוכנן" if self.is_he else "Total Planned"
        st.markdown(
            f"<div class='table-responsive'><table class='matrix-table'><thead>"
            f"<tr><th rowspan='2' style='width:18%; text-align:right;'>{schedule_parent_heading}</th>"
            f"<th colspan='4' style='width:37%;'>{month1_name}</th><th colspan='4' style='width:37%;'>{month2_name}</th>"
            f"<th rowspan='2' style='width:8%;'>{schedule_total_heading}</th></tr>"
            f"<tr><th>{self.plan_periods[0][2]}</th><th>{self.plan_periods[1][2]}</th><th>{self.plan_periods[2][2]}</th><th>{self.plan_periods[3][2]}</th>"
            f"<th>{self.plan_periods[4][2]}</th><th>{self.plan_periods[5][2]}</th><th>{self.plan_periods[6][2]}</th><th>{self.plan_periods[7][2]}</th></tr>"
            f"</thead><tbody>{rows_sched_html}</tbody></table></div>",
            unsafe_allow_html=True
        )

        with st.expander(self.translate(":material/edit_calendar: עריכת כל טבלת השבועות בבת אחת", ":material/edit_calendar: Edit All Weeks Table"), expanded=False):
            ed_s = st.data_editor(
                df_sched_sub[["W8", "W7", "W6", "W5", "W4", "W3", "W2", "W1", "parent_label"]],
                use_container_width=True, hide_index=True, key=f"{sim_key_prefix}_sched_ed"
            )
            sv1, sv2 = st.columns(2)
            with sv1:
                save_sched = st.button(":material/save: שמור תוכנית שבועות" if self.is_he else ":material/save: Save Weekly Plan", key=f"{sim_key_prefix}_sched_btn")
            with sv2:
                self.render_undo_button("schedule", f"{sim_key_prefix}_undo_sched")
            if save_sched:
                self.push_backup("schedule", self.translate("שמירת תוכנית שבועות", "Weekly plan save"))
                for _, r in ed_s.iterrows():
                    p_sku = r["parent_label"].split(" - ")[0]
                    self.conn.execute("UPDATE WeeklySchedule SET W1=?,W2=?,W3=?,W4=?,W5=?,W6=?,W7=?,W8=? WHERE parent_sku=?",
                                 (r["W1"], r["W2"], r["W3"], r["W4"], r["W5"], r["W6"], r["W7"], r["W8"], p_sku))
                self.conn.commit()
                st.rerun()

        close_hint_txt = self.translate("לחץ שוב על המספר לסגירת הבועה", "Click number again to close")
        rows_bom_html = ""
        for comp_sku, group in df_bom_view.groupby("component_sku", sort=False):
            span_count = len(group)
            is_shared = (span_count > 1)
            for idx_in_group, (row_idx, r) in enumerate(group.iterrows()):
                c_tp = r["comp_type"]
                is_w = (c_tp in ["RAW", "BULK"])
                per_unit_base = float(r["req_weight_grams"] if is_w else r["req_qty_units"])
                initial_stock_base = float(r["avail_grams"] if is_w else r["avail_units"])
                is_last_in_group = (idx_in_group == span_count - 1)
                tr_class = " class='group-end'" if is_last_in_group else ""

                child_td = ""
                init_stock_td = ""
                final_sum_td = ""

                if idx_in_group == 0:
                    if c_tp == "BULK":
                        wh_badge = f"<span class='wh-tag-bulk'>{'ממחסן בלקים (במשקל)' if self.is_he else 'From Bulks WH'}</span>"
                        col_cls = "merged-child-bulk"
                    elif c_tp == "PKG":
                        packaging_wh_label = "ממחסן אריזות (ביח')" if self.is_he else "From Packaging WH"
                        wh_badge = f"<span class='wh-tag-pkg'>{packaging_wh_label}</span>"
                        col_cls = "merged-child-col"
                    else:
                        wh_badge = f"<span class='wh-tag-pkg'>{'ממחסן חומר גלם' if self.is_he else 'From Raw WH'}</span>"
                        col_cls = "merged-child-col"

                    shared_parent_label = f'משותף ל-{span_count} מק"טי אב' if self.is_he else f"Shared by {span_count}"
                    shared_tag = (
                        f"<br><span class='shared-badge'>{shared_parent_label}</span>"
                        if is_shared else ""
                    )
                    child_td = (
                        f"<td class='{col_cls}' rowspan='{span_count}'>"
                        f"<div>{r['component_sku']}</div>"
                        f"<div style='font-size:0.82rem; font-weight:600; opacity:0.92;'>{r['comp_name']}</div>"
                        f"{wh_badge}{shared_tag}"
                        f"</td>"
                    )
                    init_stock_td = f"<td class='merged-stock-col' rowspan='{span_count}'>{self.format_value(initial_stock_base, is_w)}</td>"
                    fin_info = final_comp_balance[comp_sku]
                    fin_str = self.format_value(fin_info["after_bal"], is_w)
                    sum_cls = "summary-ok" if fin_info["is_ok"] else "summary-short"
                    final_sum_td = f"<td class='{sum_cls}' rowspan='{span_count}'>{fin_str}</td>"

                week_tds_html = ""
                for w_idx, w_col in enumerate(week_cols):
                    st_info = cell_status[(row_idx, w_col)]
                    before_str = self.format_value(st_info["before_bal"], is_w)
                    used_parent_str = self.format_value(st_info["used_parent"], is_w)
                    tot_used_str = self.format_value(st_info["tot_used_all_parents"], is_w)
                    after_str = self.format_value(st_info["after_bal"], is_w)
                    planned_parent_w = int(r[w_col])
                    wk_title = self.plan_periods[w_idx][2]

                    inc = st_info.get("incoming")
                    inc_line = ""
                    inc_badge = ""
                    if inc:
                        inc_amt_str = "+" + self.format_value(inc["amt"], is_w)
                        po_names = ", ".join(inc["pos"])
                        lbl_po = self.translate("הגעת PO", "PO arrives")
                        inc_line = f"<div style='color:#38bdf8;'>{lbl_po} ({po_names}): <b>{inc_amt_str}</b></div>"
                        inc_badge = f"<span class='cell-sub-plan'>+PO {inc_amt_str}</span>"

                    shared_line = f"<div>סה\"כ כל האבות: <b>{tot_used_str}</b></div>" if (is_shared and self.is_he) else ""
                    if self.is_he:
                        inventory_status_label = (
                            "<span style='color:#4ade80 !important;'>נשאר במלאי</span>"
                            if st_info["is_ok"]
                            else "<span style='color:#f87171 !important;'>חוסר מצטבר</span>"
                        )
                        breakdown_html = (
                            f"<div class='cell-breakdown-fit'>"
                            f"<div style='font-weight:800; color:#38bdf8 !important; margin-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.22); padding-bottom:4px;'>{r['component_sku']} ⬅ {r['parent_sku']} ({wk_title})</div>"
                            f"<div>תכנון ל-{r['parent_sku']}: <b>{planned_parent_w} {parent_unit_str}</b></div>"
                            f"{inc_line}"
                            f"<div>לפני השימוש: <b>{before_str}</b></div>"
                            f"<div>נדרש השבוע: <b>{used_parent_str}</b></div>"
                            f"{shared_line}"
                            f"<div>{inventory_status_label}: <b>{after_str}</b></div>"
                            f"<span class='bubble-close-hint'>{close_hint_txt}</span>"
                            f"</div>"
                        )
                    else:
                        breakdown_html = (
                            f"<div class='cell-breakdown-fit'>"
                            f"<div style='font-weight:800; color:#38bdf8 !important; margin-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.22); padding-bottom:4px;'>{r['component_sku']} ⬅ {r['parent_sku']} ({wk_title})</div>"
                            f"<div>Planned ({r['parent_sku']}): <b>{planned_parent_w} {parent_unit_str}</b></div>"
                            f"{inc_line}"
                            f"<div>Before usage: <b>{before_str}</b></div>"
                            f"<div>Used this week: <b>{used_parent_str}</b></div>"
                            f"<div>Balance: <b>{after_str}</b></div>"
                            f"<span class='bubble-close-hint'>{close_hint_txt}</span>"
                            f"</div>"
                        )

                    td_cls = "stock-ok" if st_info["is_ok"] else "stock-short"
                    week_tds_html += (
                        f"<td class='{td_cls}'>"
                        f"<details class='cell-details'>"
                        f"<summary><span class='cell-main-val'>{after_str}</span>{inc_badge}</summary>"
                        f"{breakdown_html}"
                        f"</details>"
                        f"</td>"
                    )

                if c_tp == "BULK" and per_unit_base < 1000:
                    per_unit_disp = f"{per_unit_base:g} {'גרם' if self.is_he else 'g'}"
                else:
                    per_unit_disp = self.format_value(per_unit_base, is_w)

                rows_bom_html += (
                    f"<tr{tr_class}>"
                    f"{child_td}"
                    f"<td style='text-align:right;'><b>{r['parent_sku']}</b> - {r['parent_name']}</td>"
                    f"<td><b>{per_unit_disp}</b></td>"
                    f"{init_stock_td}"
                    f"{week_tds_html}"
                    f"{final_sum_td}"
                    f"</tr>"
                )

        bom_child_heading = "מק\"ט בן ומחסן מקור" if self.is_he else "Child SKU & Source WH"
        bom_parent_heading = "מק\"ט אב משויך" if self.is_he else "Linked Parent"
        bom_total_heading = "סה\"כ מאזן / חוסר מצטבר" if self.is_he else "Cum. Balance"
        st.markdown(
            f"<div class='table-responsive'><table class='matrix-table'><thead>"
            f"<tr>"
            f"<th rowspan='2' style='width:15%; text-align:center;'>{bom_child_heading}</th>"
            f"<th rowspan='2' style='width:14%; text-align:right;'>{bom_parent_heading}</th>"
            f"<th rowspan='2' style='width:6%;'>{'ליחידת אב' if self.is_he else 'Per 1'}</th>"
            f"<th rowspan='2' style='width:8%;'>{'מלאי קיים במחסן' if self.is_he else 'Current Stock'}</th>"
            f"<th colspan='4' style='width:24%;'>{month1_name}</th><th colspan='4' style='width:24%;'>{month2_name}</th>"
            f"<th rowspan='2' style='width:9%;'>{bom_total_heading}</th>"
            f"</tr><tr>"
            f"<th>{self.plan_periods[0][2]}</th><th>{self.plan_periods[1][2]}</th><th>{self.plan_periods[2][2]}</th><th>{self.plan_periods[3][2]}</th>"
            f"<th>{self.plan_periods[4][2]}</th><th>{self.plan_periods[5][2]}</th><th>{self.plan_periods[6][2]}</th><th>{self.plan_periods[7][2]}</th>"
            f"</tr></thead><tbody>{rows_bom_html}</tbody></table></div>",
            unsafe_allow_html=True
        )
