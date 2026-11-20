from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import streamlit as st


def inject_stylesheet(ui: Mapping[str, str], is_collapsed: bool) -> None:
    if is_collapsed:
        sidebar_width = "68px"
    elif ui["dir"] == "rtl":
        sidebar_width = "300px"
    else:
        sidebar_width = "260px"
    replacements = {
        "__UI_DIR__": ui["dir"],
        "__UI_ALIGN__": ui["align"],
        "__SIDEBAR_WIDTH__": sidebar_width,
        "__BUTTON_JUSTIFY__": "center" if is_collapsed else "flex-start",
        "__BUTTON_PADDING__": "8px 0px" if is_collapsed else "8px 12px",
        "__BORDER_SIDE__": "right" if ui["dir"] == "rtl" else "left",
    }
    css_path = Path(__file__).resolve().parents[2] / "static" / "css" / "app.css"
    css_rules = css_path.read_text(encoding="utf-8")
    for token, value in replacements.items():
        css_rules = css_rules.replace(token, value)
    st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)
