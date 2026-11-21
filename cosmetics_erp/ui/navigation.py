from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape

import streamlit as st


def initialize_session_state() -> None:
    if "lang" not in st.session_state:
        st.session_state.lang = "he"
    if "nav_collapsed" not in st.session_state:
        st.session_state.nav_collapsed = True
    if "hover_sidebar_initialized" not in st.session_state:
        st.session_state.nav_collapsed = True
        st.session_state.hover_sidebar_initialized = True
    if "active_page" not in st.session_state:
        st.session_state.active_page = "inv"
    if "selected_weight_unit" not in st.session_state:
        st.session_state.selected_weight_unit = "kg"
    if "app_theme" not in st.session_state:
        st.session_state.app_theme = "light"


def toggle_language() -> None:
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"


def toggle_nav() -> None:
    st.session_state.nav_collapsed = not st.session_state.nav_collapsed


def save_weight_unit() -> None:
    st.session_state.selected_weight_unit = st.session_state.weight_unit_choice


def toggle_app_theme() -> None:
    st.session_state.app_theme = (
        "dark" if st.session_state.app_theme == "light" else "light"
    )


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
        ui["nav_hdr"],
        icon=collapse_icon,
        on_click=toggle_nav,
        help=collapse_help,
        key="toggle_nav_collapse",
        use_container_width=True,
    )
    st.sidebar.divider()

    active_section = None
    for section, page_key, page_icon, page_title in nav_items:
        if section != active_section:
            st.sidebar.markdown(
                f"<h3 class='nav-section-label'>{escape(section)}</h3>",
                unsafe_allow_html=True,
            )
            active_section = section
        is_active = st.session_state.active_page == page_key
        if st.sidebar.button(
            page_title,
            icon=page_icon,
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


def render_theme_toggle(ui: Mapping[str, str]) -> None:
    is_dark = st.session_state.app_theme == "dark"
    st.button(
        "",
        icon=":material/light_mode:" if is_dark else ":material/dark_mode:",
        help=(
            "מעבר למצב בהיר" if is_dark else "מעבר למצב כהה"
        ) if ui["dir"] == "rtl" else (
            "Switch to light mode" if is_dark else "Switch to dark mode"
        ),
        on_click=toggle_app_theme,
        key="floating_theme_btn",
    )
