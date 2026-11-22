from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import streamlit as st


def inject_stylesheet(ui: Mapping[str, str], is_collapsed: bool, theme: str = "light") -> None:
    if is_collapsed:
        sidebar_width = "64px"
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
        "__SIDEBAR_COLLAPSE_RULES__": """
section[data-testid="stSidebar"] > div {
    padding-inline: 0.45rem !important;
}
section[data-testid="stSidebar"] .app-brand-copy,
section[data-testid="stSidebar"] .nav-section-label,
section[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"],
section[data-testid="stSidebar"] [data-testid="stRadio"] {
    opacity: 0 !important;
    max-width: 0 !important;
    overflow: hidden !important;
    white-space: nowrap !important;
    transition: opacity 0.15s ease, max-width 0.28s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
section[data-testid="stSidebar"] .stButton button {
    justify-content: center !important;
    padding-inline: 0 !important;
}
""" if is_collapsed else "",
        "__SIDEBAR_TOUCH_RULES__": """
@media (max-width: 768px) {
    section[data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important;
        bottom: 0 !important;
        right: __SIDEBAR_FIXED_RIGHT__ !important;
        left: __SIDEBAR_FIXED_LEFT__ !important;
        width: __TOUCH_SIDEBAR_WIDTH__ !important;
        min-width: __TOUCH_SIDEBAR_WIDTH__ !important;
        max-width: __TOUCH_SIDEBAR_WIDTH__ !important;
        flex: 0 0 __TOUCH_SIDEBAR_WIDTH__ !important;
        z-index: 10000 !important;
        overflow-y: auto !important;
    }
    section[data-testid="stSidebar"] > div {
        width: __TOUCH_SIDEBAR_WIDTH__ !important;
        min-width: __TOUCH_SIDEBAR_WIDTH__ !important;
        max-width: __TOUCH_SIDEBAR_WIDTH__ !important;
        padding-inline: 0.45rem !important;
    }
    [data-testid="stMain"] .block-container {
        padding-inline-start: __TOUCH_CONTENT_GUTTER__ !important;
    }
__TOUCH_HIDDEN_NAV_RULES__
}
""" if is_collapsed else """
@media (max-width: 768px) {
    section[data-testid="stSidebar"] {
        position: fixed !important;
        top: 0 !important;
        bottom: 0 !important;
        right: __SIDEBAR_FIXED_RIGHT__ !important;
        left: __SIDEBAR_FIXED_LEFT__ !important;
        width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        min-width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        max-width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        flex: 0 0 min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        z-index: 10000 !important;
        overflow-y: auto !important;
    }
    section[data-testid="stSidebar"] > div {
        width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        min-width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
        max-width: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
    }
    [data-testid="stMain"] .block-container {
        padding-inline-start: min(__SIDEBAR_EXPANDED_WIDTH__, 85vw) !important;
    }
}
""",
        "__SIDEBAR_EXPANDED_WIDTH__": "300px" if ui["dir"] == "rtl" else "260px",
        "__SIDEBAR_FIXED_RIGHT__": "0" if ui["dir"] == "rtl" else "auto",
        "__SIDEBAR_FIXED_LEFT__": "auto" if ui["dir"] == "rtl" else "0",
        "__TOUCH_SIDEBAR_WIDTH__": "52px",
        "__TOUCH_CONTENT_GUTTER__": "3.5rem",
        "__TOUCH_HIDDEN_NAV_RULES__": """
    section[data-testid="stSidebar"] .app-brand-copy,
    section[data-testid="stSidebar"] .nav-section-label,
    section[data-testid="stSidebar"] .stButton button [data-testid="stMarkdownContainer"],
    section[data-testid="stSidebar"] [data-testid="stRadio"] {
        display: none !important;
    }
    section[data-testid="stSidebar"] .app-brand {
        justify-content: center !important;
        padding-inline: 0 !important;
    }
    section[data-testid="stSidebar"] .app-brand-mark {
        width: 32px !important;
        height: 32px !important;
        flex-basis: 32px !important;
        font-size: 1rem !important;
    }
    section[data-testid="stSidebar"] .stButton button {
        justify-content: center !important;
        padding-inline: 0 !important;
    }
""",
        "__THEME_RULES__": """
:root {
    --erp-accent: #38bdf8;
    --erp-accent-strong: #7dd3fc;
    --erp-accent-soft: #172554;
    --erp-canvas: #0f172a;
    --erp-surface: #1e293b;
    --erp-surface-muted: #334155;
    --erp-text: #f1f5f9;
    --erp-muted: #cbd5e1;
    --erp-border: #475569;
    --erp-success: #86efac;
    --erp-success-bg: #14532d;
    --erp-warning: #fde68a;
    --erp-warning-bg: #713f12;
    --erp-danger: #fca5a5;
    --erp-danger-bg: #7f1d1d;
    --erp-shadow: 0 2px 8px rgba(0, 0, 0, 0.30);
}
.stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main,
.block-container, section[data-testid="stSidebar"] {
    background: #0f172a !important;
    color: #f1f5f9 !important;
}
section[data-testid="stSidebar"] {
    background: #1e293b !important;
    border-color: #475569 !important;
}
.app-brand, .app-brand-copy strong { color: #f1f5f9 !important; }
.app-brand-copy span { color: #cbd5e1 !important; }
.app-brand { border-bottom-color: #475569 !important; }
.nav-section-label { color: #94a3b8 !important; }
section[data-testid="stSidebar"] hr { border-color: #334155 !important; }
section[data-testid="stSidebar"] [data-testid="stRadio"] {
    background: #0f172a !important;
    border-color: #475569 !important;
}
.clean-header, .plan-box, div[data-testid="stMetric"],
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stDataFrame"],
[data-testid="stDataEditor"], .table-responsive, .rtl-table,
.matrix-table, .rtl-table th, .rtl-table td, .matrix-table th,
.matrix-table td {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border-color: #475569 !important;
}
.clean-header h2, div[data-testid="stMetricValue"] > div,
.rtl-table th, .rtl-table td, .matrix-table th, .matrix-table td,
h1, h2, h3, h4, p, label, .stMarkdown, [data-testid="stMarkdownContainer"] {
    color: #f1f5f9 !important;
}
div[data-testid="stMetricLabel"] > div, [data-testid="stCaptionContainer"] {
    color: #cbd5e1 !important;
}
section[data-testid="stSidebar"] .stButton button[kind="secondary"],
section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-secondary"] {
    background: transparent !important;
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover,
section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-secondary"]:hover {
    background: #334155 !important;
    color: #7dd3fc !important;
}
section[data-testid="stSidebar"] .stButton button[data-testid="stBaseButton-primary"] {
    border-inline-start: 3px solid #38bdf8 !important;
    background: #172554 !important;
    color: #bae6fd !important;
}
div[data-baseweb="input"] > div, div[data-baseweb="select"] > div,
div[data-baseweb="textarea"] > div, div[data-baseweb="base-input"] {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border-color: #475569 !important;
}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea,
div[data-baseweb="select"] span, div[data-baseweb="base-input"] input {
    color: #f1f5f9 !important;
}
div[data-testid="stTabs"] [data-baseweb="tab-list"] { border-bottom-color: #475569; }
div[data-testid="stTabs"] button[data-baseweb="tab"] { color: #cbd5e1 !important; }
div[data-testid="stTabs"] button[aria-selected="true"] { color: #38bdf8 !important; }
.matrix-table thead tr:first-child th,
.matrix-table thead tr:nth-child(2) th,
.rtl-table th { background: #334155 !important; }
.matrix-table td.parent-col { background: #334155 !important; }
.matrix-table tbody tr:nth-child(even) td { background-color: #1e293b !important; }
.stRadio label, .stRadio [data-testid="stMarkdownContainer"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #e2e8f0 !important;
}
section[data-testid="stSidebar"] hr,
div[data-testid="stHorizontalBlock"] hr {
    border-color: #475569 !important;
}
div[data-baseweb="radio"] label,
div[role="radiogroup"] label {
    color: #f1f5f9 !important;
}
div[data-testid="stAlert"] {
    background: #1e293b !important;
    color: #f1f5f9 !important;
    border-color: #475569 !important;
}
div[data-testid="stPopoverBody"], div[data-testid="stTooltipContent"] {
    background: #1e293b !important;
    color: #f1f5f9 !important;
}
""" if theme == "dark" else "",
    }
    css_path = Path(__file__).resolve().parents[2] / "static" / "css" / "app.css"
    css_rules = css_path.read_text(encoding="utf-8")
    for token, value in replacements.items():
        css_rules = css_rules.replace(token, value)
    st.markdown(f"<style>{css_rules}</style>", unsafe_allow_html=True)
