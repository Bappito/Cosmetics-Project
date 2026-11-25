from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).resolve().parents[2] / "static" / "css" / "app.css"

# Colour tokens: the same palette as the web version, for light and dark.
_TOKENS = {
    "light": {
        "--bg": "#f5f7fb", "--surface": "#ffffff", "--surface-2": "#f8fafc", "--text": "#0f172a",
        "--muted": "#64748b", "--border": "#e6eaf2", "--primary": "#2563eb", "--primary-soft": "#eff6ff",
        "--primary-text": "#1d4ed8", "--success": "#15803d", "--success-soft": "#ecfdf3",
        "--danger": "#dc2626", "--danger-soft": "#fef2f2", "--warning": "#a16207", "--warning-soft": "#fffbeb",
        "--teal": "#0d9488", "--teal-soft": "#f0fdfa",
        "--shadow": "0 1px 2px rgba(15,23,42,.04), 0 4px 16px rgba(15,23,42,.05)",
    },
    "dark": {
        "--bg": "#0b1220", "--surface": "#111a2c", "--surface-2": "#0f1728", "--text": "#e5e7eb",
        "--muted": "#94a3b8", "--border": "#1f2c44", "--primary": "#3b82f6", "--primary-soft": "#14233d",
        "--primary-text": "#93c5fd", "--success": "#4ade80", "--success-soft": "#0f2a1d",
        "--danger": "#f87171", "--danger-soft": "#2a1313", "--warning": "#fcd34d", "--warning-soft": "#2a2110",
        "--teal": "#5eead4", "--teal-soft": "#0f2624",
        "--shadow": "0 1px 2px rgba(0,0,0,.3), 0 4px 16px rgba(0,0,0,.25)",
    },
}


def _tokens_css(theme: str) -> str:
    values = _TOKENS["dark" if theme == "dark" else "light"]
    body = "\n".join(f"  {name}: {value};" for name, value in values.items())
    return f":root {{\n{body}\n  color-scheme: {'dark' if theme == 'dark' else 'light'};\n}}"


def _collapsed_css(is_collapsed: bool) -> str:
    if not is_collapsed:
        return ""
    return """
section[data-testid="stSidebar"] > div:first-child { width: 84px !important; min-width: 84px !important; padding-inline: 10px !important; }
section[data-testid="stSidebar"] .app-brand-copy, section[data-testid="stSidebar"] .nav-section-label,
section[data-testid="stSidebar"] [data-testid="stRadio"], section[data-testid="stSidebar"] .sign-out-name { display: none !important; }
section[data-testid="stSidebar"] .app-brand { justify-content: center; padding-inline: 0; }
section[data-testid="stSidebar"] .stButton button { justify-content: center; padding-inline: 0; }
section[data-testid="stSidebar"] .stButton button p { font-size: 0 !important; }
section[data-testid="stSidebar"] .stButton button [data-testid="stIconMaterial"] { font-size: 1.5rem !important; }
"""


def inject_stylesheet(ui: Mapping[str, str], is_collapsed: bool, theme: str = "light") -> None:
    css = _CSS_PATH.read_text(encoding="utf-8")
    sidebar_width = "260px" if ui["dir"] == "ltr" else "280px"
    replacements = {
        "__THEME_TOKENS__": _tokens_css(theme),
        "__COLLAPSED_RULES__": _collapsed_css(is_collapsed),
        "__SIDEBAR_WIDTH__": sidebar_width,
    }
    for key, value in replacements.items():
        css = css.replace(key, value)
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
