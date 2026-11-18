import streamlit as st
import sqlite3
import pandas as pd
import re
import json
from datetime import datetime, timedelta, date

st.set_page_config(
    page_title="Cosmetics ERP",
    layout="wide",
    page_icon=":material/science:",
    initial_sidebar_state="expanded"
)

# --- ניהול שפה ומצב קיפול תפריט ב-Session State ---
if "lang" not in st.session_state:
    st.session_state.lang = "he"
if "nav_collapsed" not in st.session_state:
    st.session_state.nav_collapsed = False
if "active_page" not in st.session_state:
    st.session_state.active_page = "inv"

def toggle_language():
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"

def toggle_nav():
    st.session_state.nav_collapsed = not st.session_state.nav_collapsed

lang = st.session_state.lang
is_he = (lang == "he")
is_collapsed = st.session_state.nav_collapsed

def L(he_txt, en_txt):
    return he_txt if is_he else en_txt

# --- מיפוי דו-לשוני ל-8 המחסנים ולסוגי הפריטים ---
WH_NAMES = {
    "he": {
        "WH_RAW": "מחסן חומר גלם",
        "WH_BULK": "מחסן בלקים (חומר מוכן)",
        "WH_PACK": "מחסן מלאי אריזות",
        "WH_LINE": "קו ייצור",
        "WH_QA": "מחסן איכות",
        "WH_FG": "מחסן תצורה מוכנה",
        "WH_VENDOR": "מחסן ספקים",
        "WH_SCRAP": "מחסן חומרה פגומה"
    },
    "en": {
        "WH_RAW": "Raw Materials WH",
        "WH_BULK": "Bulks (Ready Material) WH",
        "WH_PACK": "Packaging Stock WH",
        "WH_LINE": "Production Line",
        "WH_QA": "Quality Assurance WH",
        "WH_FG": "Finished Goods WH",
        "WH_VENDOR": "Vendors WH",
        "WH_SCRAP": "Defective / Scrap WH"
    }
}

WH_TO_KEY = {}
for k, v in WH_NAMES["he"].items():
    WH_TO_KEY[v] = k
for k, v in WH_NAMES["en"].items():
    WH_TO_KEY[v] = k

TYPE_NAMES = {
    "he": {
        "RAW": "חומר גלם",
        "BULK": "בלק (חומר מוכן)",
        "PKG": "אריזה (בקבוק/מכסה/מתז/מדבקה)",
        "FG": "מוצר סופי ארוז"
    },
    "en": {
        "RAW": "Raw Material",
        "BULK": "Bulk (Ready Formula)",
        "PKG": "Packaging (Bottle/Cap/Pump/Label)",
        "FG": "Finished Packaged Product"
    }
}
TYPE_TO_KEY = {}
for k, v in TYPE_NAMES["he"].items():
    TYPE_TO_KEY[v] = k
for k, v in TYPE_NAMES["en"].items():
    TYPE_TO_KEY[v] = k

def tr_wh(wh_val):
    key = WH_TO_KEY.get(wh_val, wh_val)
    return WH_NAMES[lang].get(key, wh_val)

def tr_type(t_val):
    key = TYPE_TO_KEY.get(t_val, t_val)
    return TYPE_NAMES[lang].get(key, t_val)

UI = {
    "he": {
        "dir": "rtl", "align": "right",
        "nav_hdr": "תפריט ERP",
        "m_inv": "מחסנים (מלאי, תפוגה ורכש)",
        "m_sim_prod": "1. סימולטור קו ייצור",
        "m_sim_pack": "2. סימולטור אריזה",
        "m_sim_work": "3. סימולטור עבודה מסכם",
        "m_wh": "ניהול הזמנות רכש (PO) ו-SAP",
        "m_batch": "מרשם אצוות ועקיבות (FEFO)",
        "m_ai": "סוכן פקודות מהיר",
        "lang_btn": "EN | English",
        "unit_lbl": "יחידת משקל:",
        "kg": "ק\"ג (kg)", "g": "גרם (g)"
    },
    "en": {
        "dir": "ltr", "align": "left",
        "nav_hdr": "ERP Menu",
        "m_inv": "Warehouses (Stock, Expiry & PO)",
        "m_sim_prod": "1. Production Line Simulator",
        "m_sim_pack": "2. Packaging Simulator",
        "m_sim_work": "3. Master Work Simulator",
        "m_wh": "Purchase Orders (PO) & SAP",
        "m_batch": "Batches & Traceability (FEFO)",
        "m_ai": "Quick Command Agent",
        "lang_btn": "עב | עברית",
        "unit_lbl": "Weight Unit:",
        "kg": "kg", "g": "g"
    }
}[lang]

NAV_ITEMS = [
    ("inv", ":material/warehouse:", UI["m_inv"]),
    ("sim_prod", ":material/precision_manufacturing:", UI["m_sim_prod"]),
    ("sim_pack", ":material/inventory_2:", UI["m_sim_pack"]),
    ("sim_work", ":material/analytics:", UI["m_sim_work"]),
    ("wh", ":material/local_shipping:", UI["m_wh"]),
    ("batch", ":material/qr_code_2:", UI["m_batch"]),
    ("ai", ":material/terminal:", UI["m_ai"]),
]

PLAN_PERIODS = [
    ("W1", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 1 (15-21/11)" if is_he else "Week 1 (Nov 15)"),
    ("W2", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 2 (22-28/11)" if is_he else "Week 2 (Nov 22)"),
    ("W3", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 3 (29/11-05/12)" if is_he else "Week 3 (Nov 29)"),
    ("W4", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 4 (06-12/12)" if is_he else "Week 4 (Dec 06)"),
    ("W5", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 5 (13-19/12)" if is_he else "Week 5 (Dec 13)"),
    ("W6", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 6 (20-26/12)" if is_he else "Week 6 (Dec 20)"),
    ("W7", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 7 (27/12-02/01)" if is_he else "Week 7 (Dec 27)"),
    ("W8", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 8 (03-09/01)" if is_he else "Week 8 (Jan 03)"),
]

PLAN_START = date(2026, 11, 15)

def parse_date(s):
    try:
        return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None

def eta_to_week(eta_str):
    d = parse_date(eta_str)
    if d is None:
        return None
    delta = (d - PLAN_START).days
    if delta < 0:
        return "W1"
    idx = delta // 7
    return f"W{idx + 1}" if idx < 8 else None

def eta_week_label(eta_str):
    d = parse_date(eta_str)
    if d is None:
        return L("אין ETA תקין", "No valid ETA")
    wk = eta_to_week(eta_str)
    if wk is None:
        return L("מחוץ לטווח 8 השבועות", "Beyond W8")
    suffix = L(" (באיחור - נספר ב-W1)", " (overdue - counted in W1)") if d < PLAN_START else ""
    lbl = [p[2] for p in PLAN_PERIODS if p[0] == wk][0]
    return f"{wk} | {lbl}{suffix}"

# --- CSS מאוחד ונקי לחלוטין עם בועה אטומה ב-100% בעלת ניגודיות גבוהה ---
sb_w = "68px" if is_collapsed else "260px"
btn_justify = "center" if is_collapsed else "flex-start"
btn_pad = "8px 0px" if is_collapsed else "8px 12px"
border_side = "right" if is_he else "left"

css_rules = f"""
<style>
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], .main, .block-container {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    font-family: 'Segoe UI', Tahoma, sans-serif;
}}
.block-container {{
    padding-top: 0.8rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 100% !important;
}}
section[data-testid="stSidebar"] {{
    width: {sb_w} !important;
    min-width: {sb_w} !important;
    max-width: {sb_w} !important;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    transition: width 0.2s ease;
}}
section[data-testid="stSidebar"] > div {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
section[data-testid="stSidebar"] .stButton button {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    justify-content: {btn_justify} !important;
    padding: {btn_pad} !important;
    display: flex !important;
    width: 100% !important;
    border-radius: 10px !important;
}}
a.header-anchor, [data-testid="stHeaderActionElements"] {{
    display: none !important;
}}
h1, h2, h3, h4, p, label, .stMarkdown, [data-testid="stMarkdownContainer"] {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
div[data-baseweb="tab-list"], div[role="radiogroup"] {{
    direction: {UI['dir']} !important;
}}
.clean-header {{
    background: linear-gradient(135deg, var(--secondary-background-color) 0%, rgba(2, 132, 199, 0.08) 100%);
    color: var(--text-color);
    border: 1px solid rgba(128,128,128,0.22);
    border-{border_side}: 5px solid #0284c7;
    padding: 12px 18px;
    border-radius: 12px;
    margin-bottom: 14px;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
.plan-box {{
    background-color: var(--secondary-background-color);
    border: 1px solid rgba(2, 132, 199, 0.35);
    border-radius: 12px;
    padding: 12px 16px;
    margin-bottom: 14px;
}}
div[data-testid="stMetric"] {{
    background-color: var(--secondary-background-color);
    color: var(--text-color);
    border: 1px solid rgba(128,128,128,0.20);
    padding: 12px 14px;
    border-radius: 12px;
}}
div[data-testid="stMetricLabel"] > div, div[data-testid="stMetricValue"] > div {{
    color: var(--text-color) !important;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
.table-responsive {{
    width: 100%;
    overflow: visible !important;
    margin-bottom: 14px;
    border-radius: 10px;
}}
.rtl-table {{
    width: 100% !important;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: right;
    font-size: 0.88rem;
}}
.rtl-table th, .rtl-table td {{
    border: 1px solid rgba(128,128,128,0.28);
    padding: 9px 11px;
    color: var(--text-color);
    text-align: right !important;
}}
.rtl-table th {{
    background-color: var(--secondary-background-color);
    font-weight: 700;
    border-top: 3px solid #0284c7;
}}
.matrix-table {{
    width: 100% !important;
    table-layout: fixed;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: center;
    font-size: 0.84rem;
    overflow: visible !important;
}}
.matrix-table th, .matrix-table td {{
    border: 1px solid rgba(128,128,128,0.32);
    padding: 6px 4px;
    color: var(--text-color);
    word-wrap: break-word;
    overflow-wrap: break-word;
    overflow: visible !important;
}}
.matrix-table thead tr:first-child th {{
    background-color: rgba(2, 132, 199, 0.16);
    font-weight: 700;
    font-size: 0.90rem;
}}
.matrix-table thead tr:nth-child(2) th {{
    background-color: var(--secondary-background-color);
    font-weight: 600;
    font-size: 0.78rem;
}}
.matrix-table td.parent-col {{
    text-align: right !important;
    font-weight: 700;
    background-color: var(--secondary-background-color);
    padding: 8px 10px !important;
}}
.matrix-table td.merged-child-col {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    font-size: 0.90rem;
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.14) 0%, rgba(2, 132, 199, 0.04) 100%);
    border-left: 3px solid #0284c7 !important;
    padding: 8px 6px !important;
    line-height: 1.35;
}}
.matrix-table td.merged-child-bulk {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    font-size: 0.90rem;
    background: linear-gradient(135deg, rgba(168, 85, 247, 0.16) 0%, rgba(168, 85, 247, 0.04) 100%);
    border-left: 3px solid #a855f7 !important;
    padding: 8px 6px !important;
    line-height: 1.35;
}}
.matrix-table td.merged-stock-col {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    background-color: rgba(128, 128, 128, 0.07);
}}
.matrix-table tr.group-end td {{
    border-bottom: 2.5px solid rgba(2, 132, 199, 0.5) !important;
}}
.matrix-table td.stock-ok {{
    background-color: rgba(34, 197, 94, 0.20) !important;
    border: 1px solid rgba(34, 197, 94, 0.50) !important;
    padding: 6px 3px !important;
    vertical-align: middle;
    position: relative !important;
    overflow: visible !important;
    z-index: 1;
}}
.matrix-table td.stock-short {{
    background-color: rgba(239, 68, 68, 0.24) !important;
    border: 1px solid rgba(239, 68, 68, 0.60) !important;
    padding: 6px 3px !important;
    vertical-align: middle;
    position: relative !important;
    overflow: visible !important;
    z-index: 1;
}}
/* הרמת התא הפתוח והשורה שלו מעל כל שאר השורות בטבלה כך שהבועה לא תוסתר לעולם! */
.matrix-table tr:has(details[open]) {{
    z-index: 99998 !important;
    position: relative !important;
}}
.matrix-table td:has(details[open]) {{
    z-index: 99999 !important;
}}
.matrix-table td.summary-ok {{
    background-color: rgba(34, 197, 94, 0.32) !important;
    border: 2px solid rgba(34, 197, 94, 0.75) !important;
    font-weight: 800;
    font-size: 0.91rem;
    vertical-align: middle !important;
}}
.matrix-table td.summary-short {{
    background-color: rgba(239, 68, 68, 0.35) !important;
    border: 2px solid rgba(239, 68, 68, 0.80) !important;
    font-weight: 800;
    font-size: 0.91rem;
    vertical-align: middle !important;
}}
.shared-badge {{
    display: inline-block;
    margin-top: 4px;
    padding: 2px 6px;
    border-radius: 999px;
    background-color: rgba(2, 132, 199, 0.20);
    border: 1px solid rgba(2, 132, 199, 0.50);
    font-size: 0.71rem;
    font-weight: 700;
}}
.wh-tag-bulk {{
    display: inline-block;
    margin-top: 3px;
    padding: 2px 7px;
    border-radius: 6px;
    background-color: rgba(168, 85, 247, 0.20);
    border: 1px solid rgba(168, 85, 247, 0.55);
    font-size: 0.71rem;
    font-weight: 700;
}}
.wh-tag-pkg {{
    display: inline-block;
    margin-top: 3px;
    padding: 2px 7px;
    border-radius: 6px;
    background-color: rgba(2, 132, 199, 0.20);
    border: 1px solid rgba(2, 132, 199, 0.55);
    font-size: 0.71rem;
    font-weight: 700;
}}
.exp-badge-ok {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background-color: rgba(34, 197, 94, 0.18);
    border: 1px solid rgba(34, 197, 94, 0.55);
    font-size: 0.78rem;
    font-weight: 700;
}}
.exp-badge-warn {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background-color: rgba(245, 158, 11, 0.22);
    border: 1px solid rgba(245, 158, 11, 0.65);
    font-size: 0.78rem;
    font-weight: 700;
}}
.exp-badge-bad {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    background-color: rgba(239, 68, 68, 0.24);
    border: 1px solid rgba(239, 68, 68, 0.65);
    font-size: 0.78rem;
    font-weight: 700;
}}
/* --- עיצוב הבועה הצפה מעל התא עם רקע אטום לגמרי (#1e293b) וטקסט לבן בוהק --- */
.cell-details {{
    position: relative !important;
    display: block;
    cursor: pointer;
    user-select: none;
}}
.cell-details summary {{
    list-style: none;
    outline: none;
    display: block;
}}
.cell-details summary::-webkit-details-marker {{
    display: none;
}}
.cell-main-val {{
    font-size: 0.94rem;
    font-weight: 800;
    display: inline-block;
    padding: 2px 5px;
    border-radius: 6px;
    line-height: 1.22;
    transition: all 0.15s ease;
}}
.cell-details:hover .cell-main-val {{
    background-color: rgba(255, 255, 255, 0.18);
    transform: translateY(-1px);
}}
.cell-details[open] .cell-main-val {{
    box-shadow: 0 0 0 2px #38bdf8;
    background-color: rgba(56, 189, 248, 0.25);
}}
.cell-sub-plan {{
    display: block;
    font-size: 0.72rem;
    font-weight: 600;
    opacity: 0.88;
}}
/* בועה אטומה ב-100% בעלת ניגודיות גבוהה כדי שיראו את כל הנתונים בבירור מוחלט */
.cell-breakdown-fit {{
    position: absolute !important;
    bottom: calc(100% + 12px) !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    z-index: 999999 !important;
    min-width: 245px !important;
    max-width: 300px !important;
    padding: 12px 15px !important;
    border-radius: 12px !important;
    background-color: #1e293b !important;
    background: #1e293b !important;
    color: #f8fafc !important;
    opacity: 1 !important;
    backdrop-filter: none !important;
    border: 2px solid #38bdf8 !important;
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    text-align: {UI['align']} !important;
    direction: {UI['dir']} !important;
    line-height: 1.55 !important;
    box-shadow: 0 16px 36px rgba(0, 0, 0, 0.75) !important;
    white-space: normal !important;
    animation: popBubbleUp 0.15s ease-out;
}}
.cell-breakdown-fit div, .cell-breakdown-fit span, .cell-breakdown-fit b {{
    color: #f8fafc;
}}
/* חץ בתחתית הבועה שמצביע על התא */
.cell-breakdown-fit::after {{
    content: "";
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border-width: 9px;
    border-style: solid;
    border-color: #1e293b transparent transparent transparent;
}}
.bubble-close-hint {{
    display: block;
    margin-top: 7px;
    padding-top: 5px;
    border-top: 1px dashed rgba(255,255,255,0.28);
    font-size: 0.70rem;
    color: #cbd5e1 !important;
    text-align: center;
}}
@keyframes popBubbleUp {{
    from {{ opacity: 0; transform: translate(-50%, 6px) scale(0.95); }}
    to {{ opacity: 1; transform: translate(-50%, 0) scale(1); }}
}}
.legend-box {{
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.86rem;
    flex-wrap: wrap;
}}
.legend-pill-ok {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    background-color: rgba(34, 197, 94, 0.20);
    border: 1px solid rgba(34, 197, 94, 0.55);
    font-weight: 700;
}}
.legend-pill-short {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    background-color: rgba(239, 68, 68, 0.24);
    border: 1px solid rgba(239, 68, 68, 0.60);
    font-weight: 700;
}}
div.st-key-floating_lang_btn {{
    position: fixed !important;
    bottom: 16px !important;
    right: 18px !important;
    z-index: 999999 !important;
    width: auto !important;
}}
div.st-key-floating_lang_btn button {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 999px !important;
    padding: 6px 14px !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.25) !important;
}}
@media (max-width: 768px) {{
    .block-container {{
        padding-left: 0.4rem !important;
        padding-right: 0.4rem !important;
        padding-top: 0.4rem !important;
    }}
    .clean-header h2 {{
        font-size: 1.2rem !important;
    }}
    .table-responsive {{
        overflow-x: auto !important;
        padding-top: 150px !important;
        margin-top: -140px !important;
    }}
    .matrix-table {{
        min-width: 760px !important;
        font-size: 0.76rem !important;
    }}
    .rtl-table {{
        min-width: 520px !important;
        font-size: 0.80rem !important;
    }}
    div[data-testid="stMetric"] {{
        padding: 8px 10px !important;
    }}
}}
</style>
"""
st.markdown(" ".join(css_rules.split()), unsafe_allow_html=True)

DB_NAME = "cosmetics_3sim_erp.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS Catalog (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        open_orders TEXT DEFAULT '0',
        stock_movements TEXT DEFAULT '-',
        main_supplier TEXT DEFAULT '',
        alt_suppliers TEXT DEFAULT '',
        last_stock_entry TEXT DEFAULT '-',
        item_price REAL DEFAULT 0,
        min_order_qty REAL DEFAULT 1,
        last_purchase_price REAL DEFAULT 0,
        primary_warehouse TEXT DEFAULT 'WH_RAW',
        sap_code TEXT DEFAULT ''
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS BOM (
        parent_sku TEXT,
        component_sku TEXT,
        comp_type TEXT,
        req_qty_units REAL DEFAULT 0,
        req_weight_grams REAL DEFAULT 0,
        PRIMARY KEY (parent_sku, component_sku)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS WeeklySchedule (
        parent_sku TEXT PRIMARY KEY,
        W1 REAL DEFAULT 0, W2 REAL DEFAULT 0, W3 REAL DEFAULT 0, W4 REAL DEFAULT 0,
        W5 REAL DEFAULT 0, W6 REAL DEFAULT 0, W7 REAL DEFAULT 0, W8 REAL DEFAULT 0
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS PurchaseOrders (
        po_id INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number TEXT,
        sku TEXT,
        supplier TEXT,
        order_qty_units REAL DEFAULT 0,
        order_weight_grams REAL DEFAULT 0,
        unit_price REAL DEFAULT 0,
        order_date TEXT,
        eta_date TEXT,
        target_wh TEXT DEFAULT 'WH_RAW',
        status TEXT DEFAULT 'In Transit'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS StockMovements (
        move_id INTEGER PRIMARY KEY AUTOINCREMENT,
        move_date TEXT,
        sku TEXT,
        from_wh TEXT,
        to_wh TEXT,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        reference TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS Batches (
        batch_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        batch_no TEXT NOT NULL,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        expiry_date TEXT DEFAULT '',
        received_date TEXT,
        source TEXT DEFAULT 'MANUAL',
        status TEXT DEFAULT 'Active'
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS BatchConsumption (
        cons_id INTEGER PRIMARY KEY AUTOINCREMENT,
        move_date TEXT,
        parent_sku TEXT,
        parent_batch TEXT,
        component_sku TEXT,
        component_batch TEXT,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        reference TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS TableBackups (
        backup_id INTEGER PRIMARY KEY AUTOINCREMENT,
        scope TEXT,
        label TEXT,
        created_at TEXT,
        payload TEXT
    )""")

    c.execute("SELECT COUNT(*) FROM Catalog")
    if c.fetchone()[0] == 0:
        seed_items = [
            ("1001", "חמאת שיאה אורגנית / Shea Butter", "RAW", 0.0, 15000.0, "5 ק\"ג (PO-105)", "-1.2 ק\"ג לייצור", "נטורל אוילס", "בוטניקה סחר", "2026-11-10 (+10 ק\"ג)", 85.0, 5.0, 82.0, "WH_RAW", "SAP-1001"),
            ("1002", "שמן חוחובה טהור / Jojoba Oil", "RAW", 0.0, 9000.0, "0", "-0.8 ק\"ג לייצור", "נטורל אוילס", "גליל אוילס", "2026-11-08 (+5 ק\"ג)", 140.0, 3.0, 138.0, "WH_RAW", "SAP-1002"),
            ("1003", "חומצה היאלורונית / Hyaluronic Acid", "RAW", 0.0, 800.0, "5 ק\"ג (PO-101)", "-0.3 ק\"ג לייצור", "כימדע", "פארמה-כם", "2026-11-01 (+1 ק\"ג)", 1200.0, 1.0, 1150.0, "WH_RAW", "SAP-1003"),
            ("1004", "בסיס אמולסיה לקרם / Cream Base", "RAW", 0.0, 25000.0, "0", "-3.5 ק\"ג לייצור", "בוטניקה סחר", "כימדע", "2026-11-12 (+20 ק\"ג)", 45.0, 10.0, 42.0, "WH_RAW", "SAP-1004"),
            ("2001", "בלק קרם פנים היאלורוני (חומר מוכן)", "BULK", 0.0, 18000.0, "אצווה #402 (10 ק\"ג)", "+18 ק\"ג מקו ייצור", "קו ייצור פנימי", "-", "2026-11-14 (+18 ק\"ג)", 160.0, 5.0, 155.0, "WH_BULK", "SAP-2001"),
            ("2002", "בלק סרום הזנה חוחובה (חומר מוכן)", "BULK", 0.0, 12000.0, "אצווה #403 (5 ק\"ג)", "+12 ק\"ג מקו ייצור", "קו ייצור פנימי", "-", "2026-11-13 (+12 ק\"ג)", 210.0, 5.0, 200.0, "WH_BULK", "SAP-2002"),
            ("3001", "צנצנת זכוכית 50ml לקרם", "PKG", 1200.0, 0.0, "1000 יח' (PO-204)", "-200 יח' לאריזה", "אריזות המרכז", "גלאס-פק", "2026-11-05 (+1500 יח')", 2.2, 500.0, 2.1, "WH_PACK", "SAP-3001"),
            ("3002", "מכסה מוזהב לצנצנת 50ml", "PKG", 950.0, 0.0, "0", "-200 יח' לאריזה", "אריזות המרכז", "גלאס-פק", "2026-11-05 (+1000 יח')", 0.8, 500.0, 0.75, "WH_PACK", "SAP-3002"),
            ("3003", "בקבוק זכוכית 30ml לסרום", "PKG", 850.0, 0.0, "500 יח'", "-150 יח' לאריזה", "אריזות המרכז", "אקו-בוטל", "2026-11-06 (+1000 יח')", 2.0, 500.0, 1.9, "WH_PACK", "SAP-3003"),
            ("3004", "מתז / טפטפת לסרום 30ml", "PKG", 600.0, 0.0, "1000 יח'", "-150 יח' לאריזה", "אריזות המרכז", "אקו-בוטל", "2026-11-06 (+800 יח')", 1.2, 500.0, 1.1, "WH_PACK", "SAP-3004"),
            ("3005", "מדבקת חזית וברקוד (משותפת)", "PKG", 1800.0, 0.0, "2000 יח'", "-350 יח' לאריזה", "דפוס מדבקות", "פרינט-פרו", "2026-11-09 (+2000 יח')", 0.4, 1000.0, 0.38, "WH_PACK", "SAP-3005"),
            ("5001", "קרם פנים היאלורוני 50ml ארוז", "FG", 60.0, 0.0, "0", "+60 יח' מאריזה", "מחלקת אריזה", "-", "2026-11-14 (+60 יח')", 45.0, 50.0, 32.0, "WH_FG", "SAP-5001"),
            ("5002", "סרום הזנה חוחובה 30ml ארוז", "FG", 40.0, 0.0, "0", "+40 יח' מאריזה", "מחלקת אריזה", "-", "2026-11-14 (+40 יח')", 55.0, 50.0, 38.0, "WH_FG", "SAP-5002")
        ]
        c.executemany("INSERT INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", seed_items)
            
        seed_bom = [
            ("2001", "1004", "RAW", 0.0, 700.0),
            ("2001", "1001", "RAW", 0.0, 200.0),
            ("2001", "1003", "RAW", 0.0, 100.0),
            ("2002", "1002", "RAW", 0.0, 900.0),
            ("2002", "1003", "RAW", 0.0, 100.0),
            ("5001", "2001", "BULK", 0.0, 50.0),
            ("5001", "3001", "PKG", 1.0, 0.0),
            ("5001", "3002", "PKG", 1.0, 0.0),
            ("5001", "3005", "PKG", 1.0, 0.0),
            ("5002", "2002", "BULK", 0.0, 30.0),
            ("5002", "3003", "PKG", 1.0, 0.0),
            ("5002", "3004", "PKG", 1.0, 0.0),
            ("5002", "3005", "PKG", 1.0, 0.0)
        ]
        c.executemany("INSERT INTO BOM VALUES (?,?,?,?,?)", seed_bom)
        
        c.execute("INSERT INTO WeeklySchedule VALUES ('2001', 6, 8, 5, 10, 8, 7, 10, 6)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('2002', 3, 4, 4, 3, 5, 4, 3, 5)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('5001', 120, 150, 100, 200, 180, 160, 220, 140)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('5002', 80, 100, 120, 90, 110, 130, 100, 150)")
        
        today = datetime.today()
        c.execute("""
            INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("PO-101", "1003", "כימדע", 0.0, 5000.0, 1180.0, today.strftime("%Y-%m-%d"), (today + timedelta(days=5)).strftime("%Y-%m-%d"), "WH_RAW", "In Transit"))
        c.execute("""
            INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("PO-102", "3001", "אריזות המרכז", 1000.0, 0.0, 2.1, today.strftime("%Y-%m-%d"), (today + timedelta(days=10)).strftime("%Y-%m-%d"), "WH_PACK", "In Transit"))
        conn.commit()

    c.execute("SELECT COUNT(*) FROM Batches")
    if c.fetchone()[0] == 0:
        c.execute("SELECT sku, item_type, qty_units, weight_grams FROM Catalog")
        shelf_days = {"RAW": 365, "BULK": 180, "PKG": None, "FG": 730}
        today_dt = datetime.today()
        for b_sku, b_tp, b_qty, b_wg in c.fetchall():
            is_w_b = b_tp in ("RAW", "BULK")
            amt_b = b_wg if is_w_b else b_qty
            if amt_b and amt_b > 0:
                days_b = shelf_days.get(b_tp)
                exp_b = (today_dt + timedelta(days=days_b)).strftime("%Y-%m-%d") if days_b else ""
                c.execute("""
                    INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, source, status)
                    VALUES (?,?,?,?,?,?,?,'Active')
                """, (b_sku, f"OPEN-{b_sku}", 0.0 if is_w_b else b_qty, b_wg if is_w_b else 0.0,
                      exp_b, today_dt.strftime("%Y-%m-%d"), "OPENING"))
        conn.commit()
    conn.close()

init_db()
conn = get_connection()

# --- סרגל צד חכם עם אפשרות קיפול לתצוגת אייקונים בלבד ---
collapse_icon = ":material/menu_open:" if not is_collapsed else ":material/menu:"
collapse_help = L("קפל/פתח תפריט לתצוגת אייקונים בלבד", "Collapse/Expand Sidebar to Icons Only")
st.sidebar.button(
    collapse_icon if is_collapsed else f"{collapse_icon} {UI['nav_hdr']}",
    on_click=toggle_nav,
    help=collapse_help,
    use_container_width=True
)
st.sidebar.divider()

for page_key, page_icon, page_title in NAV_ITEMS:
    is_active = (st.session_state.active_page == page_key)
    btn_label = page_icon if is_collapsed else f"{page_icon} {page_title}"
    if st.sidebar.button(
        btn_label,
        key=f"nav_btn_{page_key}",
        help=page_title,
        type="primary" if is_active else "secondary",
        use_container_width=True
    ):
        st.session_state.active_page = page_key
        st.rerun()

active_page = st.session_state.active_page

st.sidebar.divider()
if not is_collapsed:
    w_choice = st.sidebar.radio(UI["unit_lbl"], [UI["kg"], UI["g"]], index=0, horizontal=True)
    use_kg = (w_choice == UI["kg"])
else:
    use_kg = True
w_factor = 1000.0 if use_kg else 1.0
w_label = ("ק\"ג" if is_he else "kg") if use_kg else ("גרם" if is_he else "g")
u_label = "יח'" if is_he else "u"

def fmt_val(val_in_base, is_weight_based):
    is_neg = (val_in_base < -1e-6)
    abs_val = abs(val_in_base)
    if is_weight_based:
        scaled = abs_val / w_factor
        num_str = f"{scaled:,.2f}".rstrip("0").rstrip(".") if use_kg else f"{scaled:,.0f}"
        unit_m = w_label
    else:
        num_str = f"{abs_val:,.0f}"
        unit_m = u_label
    if is_neg:
        return f"<span dir='ltr'>-{num_str}</span> {unit_m}"
    return f"{num_str} {unit_m}"

st.button(f":material/language: {UI['lang_btn']}", on_click=toggle_language, key="floating_lang_btn")

if "flash" in st.session_state:
    st.success(st.session_state.pop("flash"))

# ==============================================================================
# פונקציות ליבה: הזמנות רכש פתוחות, אצוות FEFO, וגיבוי Undo
# ==============================================================================
CLOSED_PO_STATUSES = ("Received", "Cancelled")

def get_incoming_map():
    df = pd.read_sql(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
        "FROM PurchaseOrders po JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received','Cancelled')", conn
    )
    out = {}
    for r in df.itertuples():
        wk = eta_to_week(r.eta_date)
        if not wk:
            continue
        is_w_po = r.item_type in ("RAW", "BULK")
        amt = float(r.order_weight_grams if is_w_po else r.order_qty_units)
        ent = out.setdefault((r.sku, wk), {"amt": 0.0, "pos": []})
        ent["amt"] += amt
        ent["pos"].append(str(r.po_number))
    return out

def get_sku_expiry_summary():
    df_b = pd.read_sql(
        "SELECT sku, batch_no, expiry_date FROM Batches WHERE status='Active' "
        "ORDER BY CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END, expiry_date ASC",
        conn
    )
    summary = {}
    today_d = date.today()
    for _, r in df_b.iterrows():
        s = r["sku"]
        if s not in summary:
            exp_s = str(r["expiry_date"] or "").strip()
            d_obj = parse_date(exp_s)
            if d_obj is None:
                badge = f"<span class='exp-badge-ok'>{L('ללא תפוגה', 'No Expiry')}</span>"
            else:
                days_l = (d_obj - today_d).days
                if days_l < 0:
                    badge = f"<span class='exp-badge-bad'>{exp_s} ({L('פג תוקף', 'Expired')})</span>"
                elif days_l <= 30:
                    badge = f"<span class='exp-badge-warn'>{exp_s} ({days_l} {L('ימים', 'days')})</span>"
                else:
                    badge = f"<span class='exp-badge-ok'>{exp_s}</span>"
            summary[s] = {"batch_no": r["batch_no"], "expiry_html": badge}
    return summary

def batch_col(is_w):
    return "weight_grams" if is_w else "qty_units"

def plan_fefo(sku, amount, is_w, allow_expired=False):
    col = batch_col(is_w)
    rows = conn.execute(
        f"SELECT batch_id, batch_no, expiry_date, {col} FROM Batches "
        f"WHERE sku=? AND status='Active' AND {col} > 0.000001 "
        f"ORDER BY CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END, expiry_date, received_date, batch_id",
        (sku,)
    ).fetchall()
    today_d = date.today()
    picks = []
    remaining = float(amount)
    for bid, bno, exp, have in rows:
        if remaining <= 1e-9:
            break
        ed = parse_date(exp)
        if ed is not None and ed < today_d and not allow_expired:
            continue
        take = min(float(have), remaining)
        picks.append({"batch_id": bid, "batch_no": bno, "expiry": exp or "", "take": take})
        remaining -= take
    return picks, max(0.0, remaining)

def apply_picks(picks, is_w):
    col = batch_col(is_w)
    for p in picks:
        conn.execute(f"UPDATE Batches SET {col} = MAX(0, {col} - ?) WHERE batch_id = ?", (p["take"], p["batch_id"]))
    conn.execute("UPDATE Batches SET status='Depleted' WHERE status='Active' AND weight_grams <= 0.000001 AND qty_units <= 0.000001")

def add_batch(sku, batch_no, amount, is_w, expiry, source):
    today_s = date.today().strftime("%Y-%m-%d")
    col = batch_col(is_w)
    row = conn.execute("SELECT batch_id FROM Batches WHERE sku=? AND batch_no=?", (sku, batch_no)).fetchone()
    if row:
        conn.execute(
            f"UPDATE Batches SET {col} = {col} + ?, status='Active', "
            f"expiry_date = CASE WHEN COALESCE(expiry_date,'')='' THEN ? ELSE expiry_date END WHERE batch_id=?",
            (amount, expiry or "", row[0])
        )
    else:
        conn.execute("""
            INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, source, status)
            VALUES (?,?,?,?,?,?,?,'Active')
        """, (sku, batch_no, 0.0 if is_w else amount, amount if is_w else 0.0, expiry or "", today_s, source))

def log_move(sku, from_wh, to_wh, amount, is_w, reference):
    conn.execute("""
        INSERT INTO StockMovements (move_date, sku, from_wh, to_wh, qty_units, weight_grams, reference)
        VALUES (?,?,?,?,?,?,?)
    """, (datetime.now().strftime("%Y-%m-%d %H:%M"), sku, from_wh, to_wh,
          0.0 if is_w else amount, amount if is_w else 0.0, reference))

def log_consumption(parent_sku, parent_batch, comp_sku, picks, is_w, reference):
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
    for p in picks:
        conn.execute("""
            INSERT INTO BatchConsumption (move_date, parent_sku, parent_batch, component_sku, component_batch, qty_units, weight_grams, reference)
            VALUES (?,?,?,?,?,?,?,?)
        """, (now_s, parent_sku, parent_batch, comp_sku, p["batch_no"],
              0.0 if is_w else p["take"], p["take"] if is_w else 0.0, reference))

def gen_batch_no(sku):
    today_s = date.today().strftime("%Y-%m-%d")
    n = conn.execute("SELECT COUNT(*) FROM Batches WHERE sku=? AND received_date=?", (sku, today_s)).fetchone()[0] + 1
    return f"L{sku}-{date.today().strftime('%y%m%d')}-{n:02d}"

def reconcile_batches():
    conn.execute("DELETE FROM Batches WHERE sku NOT IN (SELECT sku FROM Catalog)")
    cat = conn.execute("SELECT sku, item_type, qty_units, weight_grams FROM Catalog").fetchall()
    today_s = date.today().strftime("%Y-%m-%d")
    for sku, tp, qu, wg in cat:
        is_w = tp in ("RAW", "BULK")
        col = batch_col(is_w)
        target = float(wg if is_w else qu)
        cur = float(conn.execute(
            f"SELECT COALESCE(SUM({col}),0) FROM Batches WHERE sku=? AND status='Active'", (sku,)
        ).fetchone()[0] or 0)
        diff = target - cur
        if diff > 1e-6:
            add_batch(sku, f"ADJ-{sku}-{today_s.replace('-', '')}", diff, is_w, "", "ADJUST")
        elif diff < -1e-6:
            picks, _ = plan_fefo(sku, -diff, is_w, allow_expired=True)
            apply_picks(picks, is_w)
    conn.commit()

def trace_chain(sku, batch_no, direction):
    rows = []
    frontier = [(sku, batch_no)]
    seen = set(frontier)
    level = 0
    while frontier and level < 6:
        level += 1
        nxt = []
        for s, b in frontier:
            if direction == "back":
                q = conn.execute(
                    "SELECT component_sku, component_batch, qty_units, weight_grams, move_date, reference "
                    "FROM BatchConsumption WHERE parent_sku=? AND parent_batch=?", (s, b)).fetchall()
            else:
                q = conn.execute(
                    "SELECT parent_sku, parent_batch, qty_units, weight_grams, move_date, reference "
                    "FROM BatchConsumption WHERE component_sku=? AND component_batch=?", (s, b)).fetchall()
            for r in q:
                rows.append((level,) + tuple(r))
                key = (r[0], r[1])
                if key not in seen:
                    seen.add(key)
                    nxt.append(key)
        frontier = nxt
    return rows

SCOPES = {
    "stock": ["Catalog", "Batches", "BatchConsumption", "StockMovements", "PurchaseOrders"],
    "schedule": ["WeeklySchedule"],
}
MAX_BACKUPS_PER_SCOPE = 20

def push_backup(scope, label):
    payload = {}
    for t in SCOPES[scope]:
        payload[t] = json.loads(pd.read_sql(f"SELECT * FROM {t}", conn).to_json(orient="records", force_ascii=False))
    conn.execute(
        "INSERT INTO TableBackups (scope, label, created_at, payload) VALUES (?,?,?,?)",
        (scope, label, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(payload, ensure_ascii=False))
    )
    conn.execute(
        "DELETE FROM TableBackups WHERE scope=? AND backup_id NOT IN "
        "(SELECT backup_id FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT ?)",
        (scope, scope, MAX_BACKUPS_PER_SCOPE)
    )
    conn.commit()

def last_backup(scope):
    return conn.execute(
        "SELECT backup_id, label, created_at FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT 1", (scope,)
    ).fetchone()

def undo_last(scope):
    row = conn.execute(
        "SELECT backup_id, label, payload FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT 1", (scope,)
    ).fetchone()
    if not row:
        return None
    payload = json.loads(row[2])
    for t, recs in payload.items():
        conn.execute(f"DELETE FROM {t}")
        for rec in recs:
            cols = list(rec.keys())
            conn.execute(
                f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                [rec[k] for k in cols]
            )
    conn.execute("DELETE FROM TableBackups WHERE backup_id=?", (row[0],))
    conn.commit()
    return row[1]

def render_undo_button(scope, key):
    info = last_backup(scope)
    if info:
        lbl = L(f":material/undo: בטל פעולה אחרונה: {info[1]} ({info[2][5:16]})", f":material/undo: Undo last: {info[1]} ({info[2][5:16]})")
        if st.button(lbl, key=key):
            done = undo_last(scope)
            st.session_state["flash"] = L(f"שוחזר המצב שלפני: {done}", f"Restored the state before: {done}")
            st.rerun()
    else:
        st.caption(L("אין גיבוי זמין לשחזור", "No backup available to restore"))

def render_quick_planner(df_sched_sub, unit_name, key_prefix):
    st.markdown("<div class='plan-box'>", unsafe_allow_html=True)
    st.markdown(
        f"**{L('תכנון ייצור: קבע כמה את/ה מתכנן/ת לייצר ולמתי (חודש ושבוע)', 'Production Planner: Set Planned Quantity & Target Week')}**"
    )
    period_labels = [f"{p[0]} | {p[1]} - {p[2]}" for p in PLAN_PERIODS]
    c_p1, c_p2, c_p3, c_p4 = st.columns([2.2, 2.2, 1.5, 1.5])
    with c_p1:
        sel_parent_plan = st.selectbox(
            "בחר מק\"ט אב לתכנון:" if is_he else "Select Parent SKU:",
            df_sched_sub["parent_label"],
            key=f"{key_prefix}_plan_sku"
        )
    with c_p2:
        sel_week_plan = st.selectbox(
            "למתי (בחר חודש ושבוע):" if is_he else "When (Month & Week):",
            period_labels,
            key=f"{key_prefix}_plan_wk"
        )
    w_code_selected = sel_week_plan.split(" | ")[0]
    p_sku_selected = sel_parent_plan.split(" - ")[0]
    curr_planned_val = float(df_sched_sub[df_sched_sub["sku"] == p_sku_selected][w_code_selected].iloc[0])

    with c_p3:
        new_planned_qty = st.number_input(
            f"{'כמות מתוכננת' if is_he else 'Planned Qty'} ({unit_name}):",
            min_value=0.0, value=curr_planned_val, step=10.0 if unit_name == u_label else 1.0,
            key=f"{key_prefix}_plan_qty"
        )
    with c_p4:
        st.write("")
        if st.button(":material/event_available: עדכן תכנון" if is_he else ":material/event_available: Update Plan", key=f"{key_prefix}_plan_btn", use_container_width=True):
            push_backup("schedule", f"{L('תכנון', 'Plan')} {p_sku_selected} {w_code_selected}")
            conn.execute(f"UPDATE WeeklySchedule SET {w_code_selected} = ? WHERE parent_sku = ?", (new_planned_qty, p_sku_selected))
            conn.commit()
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

def render_where_used_simulator(df_sched_sub, df_bom_sub, parent_unit_str, sim_key_prefix):
    week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    month1_name = PLAN_PERIODS[0][1]
    month2_name = PLAN_PERIODS[4][1]

    render_quick_planner(df_sched_sub, parent_unit_str, sim_key_prefix)
    st.caption(L(
        "לחץ על כל תא בטבלה כדי לפתוח בועה צפה מעליו עם פירוט המלאי והשימוש באותו שבוע.",
        "Click any cell to open a floating bubble above it with the weekly breakdown."
    ))

    incoming = get_incoming_map()

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

    all_lbl = "הכל" if is_he else "All"
    child_opts = [all_lbl] + list((df_bom_sub["component_sku"] + " - " + df_bom_sub["comp_name"]).unique())
    parent_opts = [all_lbl] + list((df_sched_sub["sku"] + " - " + df_sched_sub["parent_name"]).unique())

    s1, s2, s3 = st.columns([2, 1.5, 1.5])
    with s1:
        q_search = st.text_input("חיפוש לפי מק\"ט בן או מק\"ט אב:" if is_he else "Search Child or Parent SKU:", key=f"{sim_key_prefix}_q")
    with s2:
        sel_c = st.selectbox("סנן לפי מק\"ט בן:" if is_he else "Filter Child SKU:", child_opts, key=f"{sim_key_prefix}_c")
    with s3:
        sel_p = st.selectbox("סנן לפי מק\"ט אב משויך:" if is_he else "Filter Linked Parent:", parent_opts, key=f"{sim_key_prefix}_p")

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

    st.markdown(
        f"<div class='table-responsive'><table class='matrix-table'><thead>"
        f"<tr><th rowspan='2' style='width:18%; text-align:right;'>{'מק\"ט אב ותוכנית ייצור מתוכננת' if is_he else 'Parent SKU Planned Schedule'}</th>"
        f"<th colspan='4' style='width:37%;'>{month1_name}</th><th colspan='4' style='width:37%;'>{month2_name}</th>"
        f"<th rowspan='2' style='width:8%;'>{'סה\"כ מתוכנן' if is_he else 'Total Planned'}</th></tr>"
        f"<tr><th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th></tr>"
        f"</thead><tbody>{rows_sched_html}</tbody></table></div>",
        unsafe_allow_html=True
    )

    with st.expander(L(":material/edit_calendar: עריכת כל טבלת השבועות בבת אחת", ":material/edit_calendar: Edit All Weeks Table"), expanded=False):
        ed_s = st.data_editor(
            df_sched_sub[["W8", "W7", "W6", "W5", "W4", "W3", "W2", "W1", "parent_label"]],
            use_container_width=True, hide_index=True, key=f"{sim_key_prefix}_sched_ed"
        )
        sv1, sv2 = st.columns(2)
        with sv1:
            save_sched = st.button(":material/save: שמור תוכנית שבועות" if is_he else ":material/save: Save Weekly Plan", key=f"{sim_key_prefix}_sched_btn")
        with sv2:
            render_undo_button("schedule", f"{sim_key_prefix}_undo_sched")
        if save_sched:
            push_backup("schedule", L("שמירת תוכנית שבועות", "Weekly plan save"))
            for _, r in ed_s.iterrows():
                p_sku = r["parent_label"].split(" - ")[0]
                conn.execute("UPDATE WeeklySchedule SET W1=?,W2=?,W3=?,W4=?,W5=?,W6=?,W7=?,W8=? WHERE parent_sku=?",
                             (r["W1"], r["W2"], r["W3"], r["W4"], r["W5"], r["W6"], r["W7"], r["W8"], p_sku))
            conn.commit()
            st.rerun()

    close_hint_txt = L("לחץ שוב על המספר לסגירת הבועה", "Click number again to close")
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
                    wh_badge = f"<span class='wh-tag-bulk'>{'ממחסן בלקים (במשקל)' if is_he else 'From Bulks WH'}</span>"
                    col_cls = "merged-child-bulk"
                elif c_tp == "PKG":
                    wh_badge = f"<span class='wh-tag-pkg'>{'ממחסן אריזות (ביח\')' if is_he else 'From Packaging WH'}</span>"
                    col_cls = "merged-child-col"
                else:
                    wh_badge = f"<span class='wh-tag-pkg'>{'ממחסן חומר גלם' if is_he else 'From Raw WH'}</span>"
                    col_cls = "merged-child-col"

                shared_tag = (
                    f"<br><span class='shared-badge'>{'משותף ל-' + str(span_count) + ' מק\"טי אב' if is_he else 'Shared by ' + str(span_count)}</span>"
                    if is_shared else ""
                )
                child_td = (
                    f"<td class='{col_cls}' rowspan='{span_count}'>"
                    f"<div>{r['component_sku']}</div>"
                    f"<div style='font-size:0.82rem; font-weight:600; opacity:0.92;'>{r['comp_name']}</div>"
                    f"{wh_badge}{shared_tag}"
                    f"</td>"
                )
                init_stock_td = f"<td class='merged-stock-col' rowspan='{span_count}'>{fmt_val(initial_stock_base, is_w)}</td>"
                fin_info = final_comp_balance[comp_sku]
                fin_str = fmt_val(fin_info["after_bal"], is_w)
                sum_cls = "summary-ok" if fin_info["is_ok"] else "summary-short"
                final_sum_td = f"<td class='{sum_cls}' rowspan='{span_count}'>{fin_str}</td>"

            week_tds_html = ""
            for w_idx, w_col in enumerate(week_cols):
                st_info = cell_status[(row_idx, w_col)]
                before_str = fmt_val(st_info["before_bal"], is_w)
                used_parent_str = fmt_val(st_info["used_parent"], is_w)
                tot_used_str = fmt_val(st_info["tot_used_all_parents"], is_w)
                after_str = fmt_val(st_info["after_bal"], is_w)
                planned_parent_w = int(r[w_col])
                wk_title = PLAN_PERIODS[w_idx][2]

                inc = st_info.get("incoming")
                inc_line = ""
                inc_badge = ""
                if inc:
                    inc_amt_str = "+" + fmt_val(inc["amt"], is_w)
                    po_names = ", ".join(inc["pos"])
                    lbl_po = L("הגעת PO", "PO arrives")
                    inc_line = f"<div style='color:#38bdf8;'>{lbl_po} ({po_names}): <b>{inc_amt_str}</b></div>"
                    inc_badge = f"<span class='cell-sub-plan'>+PO {inc_amt_str}</span>"

                shared_line = f"<div>סה\"כ כל האבות: <b>{tot_used_str}</b></div>" if (is_shared and is_he) else ""
                if is_he:
                    breakdown_html = (
                        f"<div class='cell-breakdown-fit'>"
                        f"<div style='font-weight:800; color:#38bdf8 !important; margin-bottom:5px; border-bottom:1px solid rgba(255,255,255,0.22); padding-bottom:4px;'>{r['component_sku']} ⬅ {r['parent_sku']} ({wk_title})</div>"
                        f"<div>תכנון ל-{r['parent_sku']}: <b>{planned_parent_w} {parent_unit_str}</b></div>"
                        f"{inc_line}"
                        f"<div>לפני השימוש: <b>{before_str}</b></div>"
                        f"<div>נדרש השבוע: <b>{used_parent_str}</b></div>"
                        f"{shared_line}"
                        f"<div>{'<span style=\"color:#4ade80 !important;\">נשאר במלאי</span>' if st_info['is_ok'] else '<span style=\"color:#f87171 !important;\">חוסר מצטבר</span>'}: <b>{after_str}</b></div>"
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
                per_unit_disp = f"{per_unit_base:g} {'גרם' if is_he else 'g'}"
            else:
                per_unit_disp = fmt_val(per_unit_base, is_w)

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

    st.markdown(
        f"<div class='table-responsive'><table class='matrix-table'><thead>"
        f"<tr>"
        f"<th rowspan='2' style='width:15%; text-align:center;'>{'מק\"ט בן ומחסן מקור' if is_he else 'Child SKU & Source WH'}</th>"
        f"<th rowspan='2' style='width:14%; text-align:right;'>{'מק\"ט אב משויך' if is_he else 'Linked Parent'}</th>"
        f"<th rowspan='2' style='width:6%;'>{'ליחידת אב' if is_he else 'Per 1'}</th>"
        f"<th rowspan='2' style='width:8%;'>{'מלאי קיים במחסן' if is_he else 'Current Stock'}</th>"
        f"<th colspan='4' style='width:24%;'>{month1_name}</th><th colspan='4' style='width:24%;'>{month2_name}</th>"
        f"<th rowspan='2' style='width:9%;'>{'סה\"כ מאזן / חוסר מצטבר' if is_he else 'Cum. Balance'}</th>"
        f"</tr><tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead><tbody>{rows_bom_html}</tbody></table></div>",
        unsafe_allow_html=True
    )

# ==============================================================================
# דף 1: מחסני המלאי מחולקים לטאבים נקיים (מלאי ותפוגה | הזמנות רכש | ספקים ותנועות | עריכה)
# ==============================================================================
if active_page == "inv":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_inv"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
    df_po_all = pd.read_sql("SELECT * FROM PurchaseOrders WHERE status NOT IN ('Received','Cancelled') ORDER BY eta_date ASC", conn)
    exp_summary_map = get_sku_expiry_summary()

    c1, c2, c3 = st.columns(3)
    raw_tot = fmt_val(df_cat[df_cat["item_type"] == "RAW"]["weight_grams"].sum(), True)
    bulk_tot = fmt_val(df_cat[df_cat["item_type"] == "BULK"]["weight_grams"].sum(), True)
    pkg_tot = fmt_val(df_cat[df_cat["item_type"] == "PKG"]["qty_units"].sum(), False)

    c1.metric(L("מחסן חומר גלם (RAW)", "Raw Materials WH"), raw_tot)
    c2.metric(L("מחסן בלקים - חומר מוכן (BULK)", "Bulks WH"), bulk_tot)
    c3.metric(L("מחסן אריזות (PKG)", "Packaging WH"), pkg_tot)

    wh_selector = st.radio(
        L("בחר מחסן לתצוגה:", "Select Warehouse:"),
        [
            L("1. מחסן חומר גלם (RAW)", "1. Raw Materials WH"),
            L("2. מחסן בלקים - חומר שהוכן (BULK)", "2. Bulks WH"),
            L("3. מחסן אריזות (PKG)", "3. Packaging WH")
        ],
        horizontal=True
    )
    active_wh_type = "RAW" if "1." in wh_selector else ("BULK" if "2." in wh_selector else "PKG")
    is_w_wh = active_wh_type in ("RAW", "BULK")
    df_wh_sub = df_cat[df_cat["item_type"] == active_wh_type]

    sub_tab_stock, sub_tab_po, sub_tab_sup, sub_tab_edit = st.tabs([
        L(":material/inventory: מלאי נוכחי ותאריכי תפוגה", ":material/inventory: Current Stock & Expiry Dates"),
        L(":material/local_shipping: הזמנות רכש (PO)", ":material/local_shipping: Purchase Orders (PO)"),
        L(":material/swap_horiz: ספקים ותנועות מלאי", ":material/swap_horiz: Suppliers & Stock Movements"),
        L(":material/edit_note: עריכה והוספת פריטים", ":material/edit_note: Edit & Add Items")
    ])

    with sub_tab_stock:
        st.subheader(L("יתרת מלאי נוכחית ותאריכי תפוגה (FEFO)", "Current Stock & Expiry Dates (FEFO)"))
        rows_stock_only = ""
        for _, r in df_wh_sub.iterrows():
            s_code = r["sku"]
            stock_str = fmt_val(r["weight_grams"] if is_w_wh else r["qty_units"], is_w_wh)
            exp_info = exp_summary_map.get(s_code, {"batch_no": "-", "expiry_html": "-"})
            rows_stock_only += (
                f"<tr>"
                f"<td><b>{s_code}</b></td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td style='font-size:1.0rem;'><b>{stock_str}</b></td>"
                f"<td>{exp_info['batch_no']}</td>"
                f"<td>{exp_info['expiry_html']}</td>"
                f"</tr>"
            )
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
            f"<th>{L('מק\"ט', 'SKU')}</th>"
            f"<th>{L('שם פריט', 'Item Name')}</th>"
            f"<th>{L('כמות מלאי נוכחית', 'Current Stock')} ({w_label if is_w_wh else u_label})</th>"
            f"<th>{L('אצווה פעילה (Batch #)', 'Active Batch #')}</th>"
            f"<th>{L('תאריך תפוגה קרוב (FEFO)', 'Nearest Expiry Date')}</th>"
            f"</tr></thead><tbody>{rows_stock_only}</tbody></table></div>",
            unsafe_allow_html=True
        )

    with sub_tab_po:
        st.subheader(L("הזמנות רכש פתוחות למחסן זה", "Open Purchase Orders for this Warehouse"))
        wh_skus = set(df_wh_sub["sku"])
        df_po_wh = df_po_all[df_po_all["sku"].isin(wh_skus)]
        if df_po_wh.empty:
            st.info(L("אין הזמנות רכש פתוחות למחסן זה כרגע.", "No open purchase orders for this warehouse."))
        else:
            po_rows_html = ""
            name_lookup = df_wh_sub.set_index("sku")["name"].to_dict()
            for _, pr in df_po_wh.iterrows():
                amt_po = fmt_val(float(pr["order_weight_grams"] if is_w_wh else pr["order_qty_units"]), is_w_wh)
                po_rows_html += (
                    f"<tr>"
                    f"<td><b>{pr['po_number']}</b></td>"
                    f"<td><b>{pr['sku']}</b> - {name_lookup.get(pr['sku'], '')}</td>"
                    f"<td>{pr['supplier']}</td>"
                    f"<td><b>{amt_po}</b></td>"
                    f"<td>{pr['eta_date']}</td>"
                    f"<td><b>{eta_week_label(pr['eta_date'])}</b></td>"
                    f"<td>{pr['status']}</td>"
                    f"</tr>"
                )
            st.markdown(
                f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
                f"<th>{L('מספר הזמנה (PO)', 'PO #')}</th>"
                f"<th>{L('פריט', 'Item')}</th>"
                f"<th>{L('ספק', 'Supplier')}</th>"
                f"<th>{L('כמות מוזמנת', 'Ordered Qty')}</th>"
                f"<th>{L('תאריך הגעה (ETA)', 'ETA Date')}</th>"
                f"<th>{L('שבוע כניסה לסימולטור', 'Simulator Arrival Week')}</th>"
                f"<th>{L('סטטוס', 'Status')}</th>"
                f"</tr></thead><tbody>{po_rows_html}</tbody></table></div>",
                unsafe_allow_html=True
            )

    with sub_tab_sup:
        st.subheader(L("ספקים, ספקים חלופיים ותנועות מלאי אחרונות", "Suppliers & Recent Stock Movements"))
        rows_sup_html = ""
        for _, r in df_wh_sub.iterrows():
            rows_sup_html += (
                f"<tr>"
                f"<td><b>{r['sku']}</b></td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td>{r['main_supplier']}</td>"
                f"<td>{r['alt_suppliers']}</td>"
                f"<td>{r['last_stock_entry']}</td>"
                f"<td>{r['stock_movements']}</td>"
                f"</tr>"
            )
        st.markdown(
            f"<div class='table-responsive'><table class='rtl-table'><thead><tr>"
            f"<th>{L('מק\"ט', 'SKU')}</th>"
            f"<th>{L('שם פריט', 'Item Name')}</th>"
            f"<th>{L('ספק ראשי', 'Main Supplier')}</th>"
            f"<th>{L('ספק חלופי', 'Alt Supplier')}</th>"
            f"<th>{L('כניסת מלאי אחרונה', 'Last Stock Entry')}</th>"
            f"<th>{L('תנועות מלאי אחרונות', 'Recent Movements')}</th>"
            f"</tr></thead><tbody>{rows_sup_html}</tbody></table></div>",
            unsafe_allow_html=True
        )

    with sub_tab_edit:
        df_ed = df_cat.copy()
        df_ed["stock_val"] = df_ed.apply(
            lambda r: round(r["weight_grams"] / w_factor, 3) if r["item_type"] in ["RAW", "BULK"] else round(r["qty_units"], 0),
            axis=1
        )
        edited_cat = st.data_editor(
            df_ed[["last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements", "open_orders", "stock_val", "item_type", "name", "sku"]],
            column_config={
                "sku": st.column_config.TextColumn("מק\"ט", required=True),
                "name": st.column_config.TextColumn("שם פריט", required=True),
                "item_type": st.column_config.SelectboxColumn("מחסן שיוך", options=["RAW", "BULK", "PKG", "FG"], required=True),
                "stock_val": st.column_config.NumberColumn(f"מלאי ({w_label} לחו\"ג ובלק / יח' לאריזה)"),
                "open_orders": st.column_config.TextColumn("הזמנות פתוחות"),
                "stock_movements": st.column_config.TextColumn("תנועות מלאי"),
                "main_supplier": st.column_config.TextColumn("ספק"),
                "alt_suppliers": st.column_config.TextColumn("ספק חלופי"),
                "last_stock_entry": st.column_config.TextColumn("כניסות מלאי אחרונות")
            },
            num_rows="dynamic", use_container_width=True, hide_index=True
        )

        kept_skus = set(str(x).strip() for x in edited_cat["sku"].dropna() if str(x).strip())
        removed_skus = sorted(set(df_cat["sku"]) - kept_skus)
        confirm_cat_del = True
        if removed_skus:
            st.warning(f"שים לב: {len(removed_skus)} פריטים יימחקו אם תשמור: {', '.join(removed_skus)}.")
            confirm_cat_del = st.checkbox("אני מאשר/ת את מחיקת הפריטים האלה", key="cat_del_confirm")

        sb1, sb2 = st.columns(2)
        with sb1:
            save_cat = st.button(":material/save: שמור שינויים בכל המחסנים", disabled=not confirm_cat_del)
        with sb2:
            render_undo_button("stock", "undo_cat")

        if save_cat:
            push_backup("stock", L("שמירת עורך מחסנים", "Warehouse editor save"))
            old_cat = df_cat.set_index("sku").to_dict("index")
            conn.execute("DELETE FROM Catalog")
            for _, r in edited_cat.iterrows():
                if pd.notna(r["sku"]) and str(r["sku"]).strip():
                    sku_s = str(r["sku"]).strip()
                    tp = str(r["item_type"] or "RAW")
                    v_num = float(r["stock_val"] or 0)
                    w_g = (v_num * w_factor) if tp in ["RAW", "BULK"] else 0.0
                    q_u = 0.0 if tp in ["RAW", "BULK"] else v_num
                    wh_k = "WH_RAW" if tp == "RAW" else ("WH_BULK" if tp == "BULK" else ("WH_PACK" if tp == "PKG" else "WH_FG"))
                    old = old_cat.get(sku_s, {})
                    conn.execute("""
                        INSERT INTO Catalog (sku, name, item_type, qty_units, weight_grams, open_orders, stock_movements, main_supplier, alt_suppliers, last_stock_entry, primary_warehouse,
                                             item_price, min_order_qty, last_purchase_price, sap_code)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (sku_s, str(r["name"]), tp, q_u, w_g, str(r["open_orders"] or "0"),
                          str(r["stock_movements"] or "-"), str(r["main_supplier"] or ""), str(r["alt_suppliers"] or ""),
                          str(r["last_stock_entry"] or "-"), wh_k,
                          float(old.get("item_price", 0) or 0), float(old.get("min_order_qty", 1) or 1),
                          float(old.get("last_purchase_price", 0) or 0), str(old.get("sap_code", "") or "")))
            conn.commit()
            reconcile_batches()
            st.session_state["flash"] = "המחסנים עודכנו בהצלחה!"
            st.rerun()

# ==============================================================================
# דף 2 (סימולטור 1): סימולטור קו ייצור
# ==============================================================================
elif active_page == "sim_prod":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_prod"]}</h2></div>', unsafe_allow_html=True)
    st.info("**סימולטור קו ייצור:** קבע כמה ק\"ג בלק את/ה מתכנן/ת לייצר ולמתי – המערכת בודקת את **מחסן חומרי הגלם (`RAW`)** ומראה מתי יהיה חוסר.")

    bulk_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'BULK'", conn)
    for _, b_r in bulk_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (b_r["sku"],))
    conn.commit()

    df_sched_prod = pd.read_sql("""
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
        WHERE c.item_type = 'BULK'
    """, conn)

    df_bom_prod = pd.read_sql("""
        SELECT b.component_sku, c.name AS comp_name, b.comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        WHERE p.item_type = 'BULK' AND c.item_type = 'RAW'
        ORDER BY b.component_sku, b.parent_sku
    """, conn)

    render_where_used_simulator(df_sched_prod, df_bom_prod, "ק\"ג בלק" if is_he else "kg Bulk", "prod")

    st.divider()
    st.subheader(L("דיווח ייצור בקו והעברת החומר המוכן למחסן בלקים", "Report Production & Transfer Ready Bulk"))
    if bulk_df.empty:
        st.warning("אין בלקים בקטלוג.")
    else:
        cp1, cp2, cp3, cp4 = st.columns([2.2, 1.2, 1.7, 1.4])
        with cp1:
            sel_bulk_make = st.selectbox("בחר בלק לייצור בקו:", bulk_df["sku"] + " - " + bulk_df["name"])
        sel_b_sku = sel_bulk_make.split(" - ")[0]
        with cp2:
            kg_to_make = st.number_input("כמות בלק לייצור (בק\"ג):", min_value=1.0, value=10.0, step=1.0)
        with cp3:
            prod_batch_in = st.text_input("מספר אצווה (Batch #) לבלק:", value=gen_batch_no(sel_b_sku), key=f"prod_bno_{sel_b_sku}")
        with cp4:
            prod_exp_in = st.date_input("תאריך תפוגה לבלק:", value=date.today() + timedelta(days=180), key="prod_exp")

        if st.button(":material/play_arrow: ייצר בלק עכשיו (גרע ממחסן חומרי גלם FEFO והעבר למחסן בלקים)"):
            b_sku = sel_b_sku
            bom_rows = pd.read_sql("SELECT component_sku, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(b_sku,))
            now_d = datetime.now().strftime("%Y-%m-%d")

            plans = []
            errors = []
            for _, br in bom_rows.iterrows():
                need_g = float(br["req_weight_grams"]) * kg_to_make
                picks, short = plan_fefo(br["component_sku"], need_g, True)
                if short > 1e-6:
                    errors.append(f"{br['component_sku']}: חסרים {short/1000:.2f} ק\"ג במלאי תקף (לא פג תוקף)")
                plans.append((br["component_sku"], need_g, picks))

            if errors:
                st.error("לא ניתן לייצר – אין מספיק חומר גלם תקף:\n\n" + "\n\n".join(errors))
            else:
                push_backup("stock", f"{L('ייצור בלק', 'Bulk production')} {b_sku} ({kg_to_make:g} {L('ק\"ג', 'kg')})")
                new_batch_no = (prod_batch_in or "").strip() or gen_batch_no(b_sku)

                limiting = None
                for _, _, picks in plans:
                    for p in picks:
                        if p["expiry"] and (limiting is None or p["expiry"] < limiting):
                            limiting = p["expiry"]
                exp_s = prod_exp_in.strftime("%Y-%m-%d")
                capped = False
                if limiting and exp_s > limiting:
                    exp_s = limiting
                    capped = True

                for comp_sku, need_g, picks in plans:
                    apply_picks(picks, True)
                    log_consumption(b_sku, new_batch_no, comp_sku, picks, True, f"PROD {b_sku}")
                    log_move(comp_sku, "WH_RAW", "WH_LINE", need_g, True, f"PROD {b_sku} / {new_batch_no}")
                    conn.execute("""
                        UPDATE Catalog
                        SET weight_grams = MAX(0, weight_grams - ?),
                            stock_movements = ?
                        WHERE sku = ?
                    """, (need_g, f"-{need_g/1000:.2f} ק\"ג לבלק {b_sku}", comp_sku))

                produced_g = kg_to_make * 1000.0
                add_batch(b_sku, new_batch_no, produced_g, True, exp_s, "PRODUCTION")
                log_move(b_sku, "WH_LINE", "WH_BULK", produced_g, True, f"PROD {b_sku} / {new_batch_no}")
                conn.execute("""
                    UPDATE Catalog
                    SET weight_grams = weight_grams + ?,
                        stock_movements = ?,
                        last_stock_entry = ?
                    WHERE sku = ?
                """, (produced_g, f"+{kg_to_make:.1f} ק\"ג מקו ייצור", f"{now_d} (+{kg_to_make:.1f} ק\"ג)", b_sku))
                conn.commit()
                msg = f"יוצרו {kg_to_make} ק\"ג של בלק {b_sku} באצווה {new_batch_no} (תפוגה {exp_s}). חומרי הגלם נגרעו לפי FEFO והבלק הועבר למחסן בלקים."
                if capped:
                    msg += f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של חומר הגלם ({limiting})."
                st.session_state["flash"] = msg
                st.rerun()

# ==============================================================================
# דף 3 (סימולטור 2): סימולטור אריזה
# ==============================================================================
elif active_page == "sim_pack":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_pack"]}</h2></div>', unsafe_allow_html=True)
    st.info("**סימולטור אריזה משולב:** קבע כמה יחידות מוצר סופי את/ה מתכנן/ת לארוז ולמתי – המערכת בודקת במקביל את **החומר המוכן ממחסן הבלקים (`BULK`)** ואת **האריזות ממחסן האריזות (`PKG`)**.")

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
        st.warning("אין מוצרים סופיים בקטלוג.")
    else:
        ck1, ck2, ck3, ck4 = st.columns([2.2, 1.2, 1.7, 1.4])
        with ck1:
            sel_fg_pack = st.selectbox("בחר מוצר סופי לאריזה:", fg_df["sku"] + " - " + fg_df["name"])
        sel_f_sku = sel_fg_pack.split(" - ")[0]
        with ck2:
            units_to_pack = st.number_input("כמות יחידות למילוי ואריזה:", min_value=1, value=100, step=10)
        with ck3:
            pack_batch_in = st.text_input("מספר אצווה (Batch #) למוצר:", value=gen_batch_no(sel_f_sku), key=f"pack_bno_{sel_f_sku}")
        with ck4:
            pack_exp_in = st.date_input("תאריך תפוגה למוצר:", value=date.today() + timedelta(days=730), key="pack_exp")

        if st.button(":material/check_circle: בצע אריזה (גרע בלק ממחסן בלקים + בקבוקים/מכסים/מדבקות ממחסן אריזות)"):
            f_sku = sel_f_sku
            bom_p = pd.read_sql("SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(f_sku,))
            now_d = datetime.now().strftime("%Y-%m-%d")

            plans = []
            errors = []
            for _, br in bom_p.iterrows():
                is_w_c = (br["comp_type"] == "BULK")
                need = float(br["req_weight_grams"] if is_w_c else br["req_qty_units"]) * units_to_pack
                picks, short = plan_fefo(br["component_sku"], need, is_w_c)
                if short > 1e-6:
                    short_txt = f"{short/1000:.2f} ק\"ג" if is_w_c else f"{short:.0f} יח'"
                    errors.append(f"{br['component_sku']}: חסרים {short_txt} במלאי תקף (לא פג תוקף)")
                plans.append((br["component_sku"], is_w_c, need, picks))

            if errors:
                st.error("לא ניתן לבצע אריזה – אין מספיק רכיבים תקפים:\n\n" + "\n\n".join(errors))
            else:
                push_backup("stock", f"{L('אריזת', 'Packing')} {f_sku} ({units_to_pack} {u_label})")
                new_batch_no = (pack_batch_in or "").strip() or gen_batch_no(f_sku)

                limiting = None
                for _, _, _, picks in plans:
                    for p in picks:
                        if p["expiry"] and (limiting is None or p["expiry"] < limiting):
                            limiting = p["expiry"]
                exp_s = pack_exp_in.strftime("%Y-%m-%d")
                capped = False
                if limiting and exp_s > limiting:
                    exp_s = limiting
                    capped = True

                for comp_sku, is_w_c, need, picks in plans:
                    apply_picks(picks, is_w_c)
                    log_consumption(f_sku, new_batch_no, comp_sku, picks, is_w_c, f"PACK {f_sku}")
                    log_move(comp_sku, "WH_BULK" if is_w_c else "WH_PACK", "WH_LINE", need, is_w_c, f"PACK {f_sku} / {new_batch_no}")
                    if is_w_c:
                        conn.execute("UPDATE Catalog SET weight_grams = MAX(0, weight_grams - ?), stock_movements = ? WHERE sku = ?",
                                     (need, f"-{need/1000:.2f} ק\"ג לאריזת {f_sku}", comp_sku))
                    else:
                        conn.execute("UPDATE Catalog SET qty_units = MAX(0, qty_units - ?), stock_movements = ? WHERE sku = ?",
                                     (need, f"-{need:.0f} יח' לאריזת {f_sku}", comp_sku))

                add_batch(f_sku, new_batch_no, float(units_to_pack), False, exp_s, "PACKING")
                log_move(f_sku, "WH_LINE", "WH_FG", float(units_to_pack), False, f"PACK {f_sku} / {new_batch_no}")
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku = ?",
                             (units_to_pack, f"{now_d} (+{units_to_pack} יח')", f_sku))
                conn.commit()
                msg = f"נארזו {units_to_pack} יח' של {f_sku} באצווה {new_batch_no} (תפוגה {exp_s}). המלאי נגרע ממחסן הבלקים וממחסן האריזות לפי FEFO."
                if capped:
                    msg += f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של הרכיבים ({limiting})."
                st.session_state["flash"] = msg
                st.rerun()

# ==============================================================================
# דף 4 (סימולטור 3): סימולטור עבודה מסכם (עם בועה צפה אטומה מעל התא!)
# ==============================================================================
elif active_page == "sim_work":
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

    work_matrix_html = (
        f"<div class='table-responsive'><table class='matrix-table'><thead>"
        f"<tr>"
        f"<th rowspan='2' style='width:16%; text-align:right;'>{'מק\"ט אב ושם מוצר' if is_he else 'Parent SKU & Name'}</th>"
        f"<th colspan='4' style='width:37%;'>{month1_name}</th>"
        f"<th colspan='4' style='width:37%;'>{month2_name}</th>"
        f"<th rowspan='2' style='width:10%;'>{'סה\"כ תקופתי (אפשרי מול מתוכנן)' if is_he else 'Total Makeable vs Planned'}</th>"
        f"</tr><tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead><tbody>{rows_work_html}</tbody></table></div>"
    )
    st.markdown(work_matrix_html, unsafe_allow_html=True)

# ==============================================================================
# דף 5: העברות בין מחסנים, הזמנות רכש ו-SAP
# ==============================================================================
elif active_page == "wh":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    cat_meta = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn).set_index("sku")

    st.subheader(L("הזמנות רכש פתוחות ושבוע ההגעה שלהן בסימולטורים", "Open POs & Arrival Week in Simulators"))
    open_df = df_po[~df_po["status"].isin(list(CLOSED_PO_STATUSES))]
    if open_df.empty:
        st.caption(L("אין הזמנות רכש פתוחות.", "No open purchase orders."))
    else:
        view_rows = []
        for r in open_df.itertuples():
            tp = cat_meta.loc[r.sku]["item_type"] if r.sku in cat_meta.index else "RAW"
            nm = cat_meta.loc[r.sku]["name"] if r.sku in cat_meta.index else "?"
            is_w_po = tp in ("RAW", "BULK")
            amt_plain = fmt_val(float(r.order_weight_grams if is_w_po else r.order_qty_units), is_w_po)
            view_rows.append({
                L("הזמנה", "PO"): r.po_number,
                L("מק\"ט", "SKU"): r.sku,
                L("פריט", "Item"): nm,
                L("ספק", "Supplier"): r.supplier,
                L("כמות", "Qty"): amt_plain,
                "ETA": r.eta_date,
                L("נכנס למאזן בשבוע", "Counted in week"): eta_week_label(r.eta_date),
                L("סטטוס", "Status"): r.status,
            })
        st.dataframe(pd.DataFrame(view_rows), use_container_width=True, hide_index=True)

    st.subheader(L("עריכת הזמנות רכש", "Edit purchase orders"))
    ed_po = st.data_editor(
        df_po, use_container_width=True, hide_index=True, num_rows="dynamic", key="po_editor",
        column_config={
            "status": st.column_config.SelectboxColumn("status", options=["In Transit", "Confirmed", "Received", "Cancelled"]),
        }
    )

    kept_pos = set(str(x).strip() for x in ed_po["po_number"].dropna() if str(x).strip())
    removed_pos = sorted(set(str(x) for x in df_po["po_number"].dropna()) - kept_pos)
    confirm_po_del = True
    if removed_pos:
        st.warning(f"{len(removed_pos)} הזמנות יימחקו אם תשמור: {', '.join(removed_pos)}.")
        confirm_po_del = st.checkbox("אני מאשר/ת את מחיקת ההזמנות האלה", key="po_del_confirm")

    pb1, pb2 = st.columns(2)
    with pb1:
        save_po = st.button(":material/save: שמור הזמנות רכש", disabled=not confirm_po_del)
    with pb2:
        render_undo_button("stock", "undo_po")

    if save_po:
        push_backup("stock", L("שמירת הזמנות רכש", "PO save"))
        conn.execute("DELETE FROM PurchaseOrders")
        for _, r in ed_po.iterrows():
            if pd.notna(r["po_number"]) and pd.notna(r["sku"]):
                conn.execute("""
                    INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                """, (str(r["po_number"]), str(r["sku"]), str(r["supplier"] or ""), float(r["order_qty_units"] or 0),
                      float(r["order_weight_grams"] or 0), float(r["unit_price"] or 0), str(r["order_date"] or ""),
                      str(r["eta_date"] or ""), str(r["target_wh"] or "WH_RAW"), str(r["status"] or "In Transit")))
        conn.commit()
        st.session_state["flash"] = "נשמר!"
        st.rerun()

    st.divider()
    st.subheader(L("קבלת הזמנה למחסן (יוצר אצווה + תפוגה)", "Receive PO into warehouse (creates batch + expiry)"))
    if not open_df.empty:
        po_opts = [f"{r.po_number} | {r.sku}" for r in open_df.itertuples()]
        sel_po = st.selectbox(L("בחר הזמנה לקבלה:", "Select PO to receive:"), po_opts, key="rcv_po_sel")
        sel_po_num = sel_po.split(" | ")[0]
        po_row = open_df[open_df["po_number"] == sel_po_num].iloc[0]
        rcv_sku = str(po_row["sku"])
        rcv_tp = cat_meta.loc[rcv_sku]["item_type"] if rcv_sku in cat_meta.index else None
        if rcv_tp is not None:
            rcv_is_w = rcv_tp in ("RAW", "BULK")
            rcv_amt = float(po_row["order_weight_grams"] if rcv_is_w else po_row["order_qty_units"])
            rc1, rc2, rc3 = st.columns([2, 1.5, 1.5])
            with rc1:
                rcv_batch = st.text_input(L("מספר אצווה (Batch #) מהספק:", "Supplier Batch #:"),
                                          value=f"LOT-{rcv_sku}-{sel_po_num}", key=f"rcv_bno_{sel_po_num}")
            with rc2:
                rcv_exp = st.date_input(L("תאריך תפוגה:", "Expiry date:"),
                                        value=date.today() + timedelta(days=365), key=f"rcv_exp_{sel_po_num}")
            with rc3:
                rcv_no_exp = st.checkbox(L("ללא תפוגה", "No expiry"), value=(rcv_tp == "PKG"), key=f"rcv_noexp_{sel_po_num}")
            if st.button(L(":material/download_done: קבל למחסן", ":material/download_done: Receive into warehouse"), key="rcv_btn"):
                push_backup("stock", f"{L('קבלת', 'Receive')} {sel_po_num}")
                bno = (rcv_batch or "").strip() or gen_batch_no(rcv_sku)
                exp_s = "" if rcv_no_exp else rcv_exp.strftime("%Y-%m-%d")
                add_batch(rcv_sku, bno, rcv_amt, rcv_is_w, exp_s, "PO")
                log_move(rcv_sku, "WH_VENDOR", str(po_row["target_wh"] or "WH_RAW"), rcv_amt, rcv_is_w, f"{sel_po_num} / {bno}")
                now_d = datetime.now().strftime("%Y-%m-%d")
                if rcv_is_w:
                    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                                 (rcv_amt, f"+{rcv_amt/1000:.2f} ק\"ג מקבלת {sel_po_num}", f"{now_d} (+{rcv_amt/1000:.2f} ק\"ג)", rcv_sku))
                else:
                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                                 (rcv_amt, f"+{rcv_amt:.0f} יח' מקבלת {sel_po_num}", f"{now_d} (+{rcv_amt:.0f} יח')", rcv_sku))
                conn.execute("UPDATE PurchaseOrders SET status='Received' WHERE po_number=?", (sel_po_num,))
                conn.commit()
                st.session_state["flash"] = f"הזמנה {sel_po_num} התקבלה: אצווה {bno}, תפוגה {exp_s or 'ללא'}."
                st.rerun()

# ==============================================================================
# דף 6: אצוות ותוקף (Batch / Lot & Expiry) + עקיבות
# ==============================================================================
elif active_page == "batch":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_batch"]}</h2></div>', unsafe_allow_html=True)

    df_b = pd.read_sql(
        "SELECT b.*, c.name, c.item_type FROM Batches b JOIN Catalog c ON b.sku = c.sku", conn
    )
    today_d = date.today()

    def days_left_fn(s):
        d_ = parse_date(s)
        return (d_ - today_d).days if d_ else None

    if not df_b.empty:
        df_b["days_left"] = df_b["expiry_date"].apply(days_left_fn)
    active_b = df_b[df_b["status"] == "Active"] if not df_b.empty else df_b
    n_active = len(active_b)
    n_expired = int((active_b["days_left"] < 0).sum()) if n_active else 0
    n_soon = int(((active_b["days_left"] >= 0) & (active_b["days_left"] <= 30)).sum()) if n_active else 0

    m1, m2, m3 = st.columns(3)
    m1.metric(L("אצוות פעילות", "Active batches"), n_active)
    m2.metric(L("פגות תוקף תוך 30 יום", "Expiring within 30 days"), n_soon)
    m3.metric(L("פגות תוקף (חסומות לשימוש)", "Expired (blocked)"), n_expired)

    t_b1, t_b2, t_b3 = st.tabs([
        L(":material/list_alt: מלאי לפי אצווה (FEFO)", ":material/list_alt: Stock by batch (FEFO)"),
        L(":material/add_box: כניסת מלאי ידנית עם אצווה", ":material/add_box: Manual receipt with batch"),
        L(":material/account_tree: עקיבות (Traceability)", ":material/account_tree: Traceability"),
    ])

    with t_b1:
        if not df_b.empty:
            fc1, fc2 = st.columns([2, 1])
            with fc1:
                sku_opts = [L("הכל", "All")] + sorted(df_b["sku"].unique())
                sel_sku_b = st.selectbox(L("סנן לפי מק\"ט:", "Filter by SKU:"), sku_opts, key="batch_sku_filter")
            with fc2:
                show_depleted = st.checkbox(L("הצג גם אצוות שנוצלו", "Include depleted batches"), key="batch_show_dep")
            view_b = df_b.copy()
            if sel_sku_b != L("הכל", "All"):
                view_b = view_b[view_b["sku"] == sel_sku_b]
            if not show_depleted:
                view_b = view_b[view_b["status"] == "Active"]
            if not view_b.empty:
                view_b = view_b.assign(_noexp=view_b["expiry_date"].fillna("").eq("")).sort_values(["sku", "_noexp", "expiry_date", "batch_id"])
                out_rows = []
                for _, r in view_b.iterrows():
                    is_w_b = r["item_type"] in ("RAW", "BULK")
                    dl = r["days_left"]
                    out_rows.append({
                        L("מק\"ט", "SKU"): r["sku"],
                        L("פריט", "Item"): r["name"],
                        "Batch #": r["batch_no"],
                        L("יתרה", "Remaining"): fmt_val(float(r["weight_grams"] if is_w_b else r["qty_units"]), is_w_b),
                        L("תפוגה", "Expiry"): r["expiry_date"] or "-",
                        L("ימים לתפוגה", "Days left"): "-" if (dl is None or pd.isna(dl)) else str(int(dl)),
                        L("מקור", "Source"): r["source"],
                        L("תאריך כניסה", "Received"): r["received_date"],
                    })
                st.dataframe(pd.DataFrame(out_rows), use_container_width=True, hide_index=True)
        render_undo_button("stock", "undo_batches")

    with t_b2:
        cat_b = pd.read_sql("SELECT sku, name, item_type FROM Catalog ORDER BY sku", conn)
        sel_mb = st.selectbox(L("מק\"ט לכניסת מלאי:", "SKU to receive:"), cat_b["sku"] + " - " + cat_b["name"], key="mb_sku")
        mb_sku = sel_mb.split(" - ")[0]
        mb_tp = cat_b[cat_b["sku"] == mb_sku].iloc[0]["item_type"]
        mb_is_w = mb_tp in ("RAW", "BULK")
        mb1, mb2, mb3, mb4 = st.columns([1.4, 1.8, 1.5, 1.2])
        with mb1:
            mb_amt = st.number_input(
                L(f"כמות ({w_label})", f"Quantity ({w_label})") if mb_is_w else L("כמות (יח')", "Quantity (units)"),
                min_value=0.0, value=1.0, step=1.0, key=f"mb_amt_{mb_sku}"
            )
        with mb2:
            mb_bno = st.text_input("Batch #", value=gen_batch_no(mb_sku), key=f"mb_bno_{mb_sku}")
        with mb3:
            mb_exp = st.date_input(L("תאריך תפוגה", "Expiry date"), value=date.today() + timedelta(days=365), key=f"mb_exp_{mb_sku}")
        with mb4:
            mb_noexp = st.checkbox(L("ללא תפוגה", "No expiry"), value=(mb_tp == "PKG"), key=f"mb_noexp_{mb_sku}")
        if st.button(L(":material/add: הוסף למלאי", ":material/add: Add to stock"), key="mb_btn"):
            if mb_amt > 0:
                push_backup("stock", f"{L('כניסת מלאי', 'Receipt')} {mb_sku}")
                base_amt = mb_amt * w_factor if mb_is_w else mb_amt
                bno = (mb_bno or "").strip() or gen_batch_no(mb_sku)
                exp_s = "" if mb_noexp else mb_exp.strftime("%Y-%m-%d")
                add_batch(mb_sku, bno, base_amt, mb_is_w, exp_s, "MANUAL")
                now_d = datetime.now().strftime("%Y-%m-%d")
                if mb_is_w:
                    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ?, last_stock_entry = ? WHERE sku=?",
                                 (base_amt, f"{now_d} (+{base_amt/1000:.2f} ק\"ג)", mb_sku))
                else:
                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku=?",
                                 (base_amt, f"{now_d} (+{base_amt:.0f} יח')", mb_sku))
                conn.commit()
                st.session_state["flash"] = f"נוספה אצווה {bno} למק\"ט {mb_sku}."
                st.rerun()

    with t_b3:
        if not df_b.empty:
            tc1, tc2 = st.columns(2)
            with tc1:
                tr_sku = st.selectbox(L("מק\"ט:", "SKU:"), sorted(df_b["sku"].unique()), key="tr_sku")
            with tc2:
                tr_batch = st.selectbox("Batch #:", list(df_b[df_b["sku"] == tr_sku]["batch_no"]), key=f"tr_batch_{tr_sku}")
            name_map = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn).set_index("sku")

            def trace_df(rows):
                out = []
                for lvl, s, b, qu, wg, mdt, ref in rows:
                    is_w_t = (name_map.loc[s]["item_type"] in ("RAW", "BULK")) if s in name_map.index else False
                    out.append({
                        L("רמה", "Level"): lvl,
                        L("מק\"ט", "SKU"): s,
                        L("פריט", "Item"): name_map.loc[s]["name"] if s in name_map.index else "?",
                        "Batch #": b,
                        L("כמות", "Qty"): fmt_val(float(wg if is_w_t else qu), is_w_t),
                        L("תאריך", "Date"): mdt,
                        L("אסמכתא", "Reference"): ref,
                    })
                return pd.DataFrame(out)

            back_rows = trace_chain(tr_sku, tr_batch, "back")
            fwd_rows = trace_chain(tr_sku, tr_batch, "fwd")
            st.markdown(f"**{L('ממה הוכנה האצווה (אחורה)', 'Made from (backward)')}**")
            if back_rows:
                st.dataframe(trace_df(back_rows), use_container_width=True, hide_index=True)
            else:
                st.caption(L("אין רשומות (חומר גלם נכנס או מלאי פתיחה).", "No records."))
            st.markdown(f"**{L('לאילו אצוות נכנסה (קדימה)', 'Went into (forward)')}**")
            if fwd_rows:
                st.dataframe(trace_df(fwd_rows), use_container_width=True, hide_index=True)
            else:
                st.caption(L("האצווה עדיין לא נצרכה באף אצוות מוצר.", "Not consumed yet."))

# ==============================================================================
# דף 7: סוכן פקודות מהיר
# ==============================================================================
elif active_page == "ai":
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_ai"]}</h2></div>', unsafe_allow_html=True)
    st.caption("כתוב פקודה כגון: `תוסיף 5 קילו ל-1001` או `תוסיף 10 קילו ל-2001` או `תוסיף 300 יחידות ל-3001`")
    render_undo_button("stock", "undo_agent")
    cmd_in = st.chat_input("כתוב פקודה לביצוע מיידי...")
    if cmd_in:
        nums = re.findall(r"(\d+(?:\.\d+)?)", cmd_in)
        if len(nums) >= 2:
            s_code = nums[-1]
            val = float(nums[0])
            exists = conn.execute("SELECT item_type FROM Catalog WHERE sku=?", (s_code,)).fetchone()
            if not exists:
                st.error(f"מק\"ט {s_code} לא קיים בקטלוג.")
            else:
                push_backup("stock", f"{L('פקודת סוכן', 'Agent command')}: {cmd_in[:40]}")
                if "קילו" in cmd_in or "kg" in cmd_in.lower():
                    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?", (val * 1000.0, s_code))
                    conn.commit()
                    msg_a = f"נוספו {val} ק\"ג למק\"ט {s_code}!"
                else:
                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?", (val, s_code))
                    conn.commit()
                    msg_a = f"נוספו {val} יח' למק\"ט {s_code}!"
                reconcile_batches()
                st.success(msg_a)
