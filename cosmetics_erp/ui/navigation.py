from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape

import streamlit as st


def initialize_session_state() -> None:
    if "lang" not in st.session_state:
        st.session_state.lang = "he"
    if "nav_collapsed" not in st.session_state:
        st.session_state.nav_collapsed = False
    if "active_page" not in st.session_state:
        st.session_state.active_page = "inv"
    if "selected_weight_unit" not in st.session_state:
        st.session_state.selected_weight_unit = "kg"


def toggle_language() -> None:
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"


def toggle_nav() -> None:
    st.session_state.nav_collapsed = not st.session_state.nav_collapsed


def save_weight_unit() -> None:
    st.session_state.selected_weight_unit = st.session_state.weight_unit_choice


def render_sidebar(
    ui: Mapping[str, str],
    nav_items: Sequence[tuple[str, str, str, str]],
    is_collapsed: bool,
) -> tuple[str, bool]:
    collapse_icon = ":material/menu_open:" if not is_collapsed else ":material/menu:"
    collapse_help = (
        "קפל/פתח תפריט לתצוגת אייקונים בלבד"
        if ui["dir"] == "rtl"
        else "Collapse/Expand Sidebar to Icons Only"
    )
    if is_collapsed:
        st.sidebar.markdown(
            "<div class='app-brand'><div class='app-brand-mark'>C</div></div>",
            unsafe_allow_html=True,
        )
    else:
        brand_subtitle = (
            "מערכת תפעול וייצור"
            if ui["dir"] == "rtl"
            else "Operations &amp; Manufacturing"
        )
        st.sidebar.markdown(
            "<div class='app-brand'><div class='app-brand-mark'>C</div>"
            "<div class='app-brand-copy'><strong>Cosmetics ERP</strong>"
            f"<span>{brand_subtitle}</span></div></div>",
            unsafe_allow_html=True,
        )
    st.sidebar.button(
        collapse_icon if is_collapsed else f"{collapse_icon} {ui['nav_hdr']}",
        on_click=toggle_nav,
        help=collapse_help,
        key="toggle_nav_collapse",
        use_container_width=True,
    )
    st.sidebar.divider()

    active_section = None
    for section, page_key, page_icon, page_title in nav_items:
        if not is_collapsed and section != active_section:
            st.sidebar.markdown(
                f"<h3 class='nav-section-label'>{escape(section)}</h3>",
                unsafe_allow_html=True,
            )
            active_section = section
        is_active = st.session_state.active_page == page_key
        btn_label = page_icon if is_collapsed else f"{page_icon} {page_title}"
        if st.sidebar.button(
            btn_label,
            key=f"nav_btn_{page_key}",
            help=page_title,
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            st.session_state.active_page = page_key
            st.rerun()

    st.sidebar.divider()
    if not is_collapsed:
        st.session_state.weight_unit_choice = st.session_state.selected_weight_unit
        st.sidebar.radio(
            ui["unit_lbl"],
            ["kg", "g"],
            format_func=lambda unit: ui[unit],
            key="weight_unit_choice",
            on_change=save_weight_unit,
            horizontal=True,
        )
    use_kg = st.session_state.selected_weight_unit == "kg"
    return st.session_state.active_page, use_kg


def render_language_toggle(ui: Mapping[str, str]) -> None:
    st.button(
        f":material/language: {ui['lang_btn']}",
        on_click=toggle_language,
        key="floating_lang_btn",
    )
