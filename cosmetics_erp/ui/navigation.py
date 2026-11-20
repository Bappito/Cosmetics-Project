from __future__ import annotations

from collections.abc import Mapping, Sequence

import streamlit as st


def initialize_session_state() -> None:
    if "lang" not in st.session_state:
        st.session_state.lang = "he"
    if "nav_collapsed" not in st.session_state:
        st.session_state.nav_collapsed = False
    if "active_page" not in st.session_state:
        st.session_state.active_page = "inv"


def toggle_language() -> None:
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"


def toggle_nav() -> None:
    st.session_state.nav_collapsed = not st.session_state.nav_collapsed


def render_sidebar(
    ui: Mapping[str, str],
    nav_items: Sequence[tuple[str, str, str]],
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
        use_container_width=True,
    )
    st.sidebar.divider()

    for page_key, page_icon, page_title in nav_items:
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
    if is_collapsed:
        use_kg = True
    else:
        weight_choice = st.sidebar.radio(
            ui["unit_lbl"],
            [ui["kg"], ui["g"]],
            index=0,
            horizontal=True,
        )
        use_kg = weight_choice == ui["kg"]
    return st.session_state.active_page, use_kg


def render_language_toggle(ui: Mapping[str, str]) -> None:
    st.button(
        f":material/language: {ui['lang_btn']}",
        on_click=toggle_language,
        key="floating_lang_btn",
    )
