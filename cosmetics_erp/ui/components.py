from __future__ import annotations

import sqlite3
from typing import Any, Callable, Sequence

import streamlit as st

from cosmetics_erp.ui.planner import PlannerMixin


class UIComponents(PlannerMixin):
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
