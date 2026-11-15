import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Cosmetics ERP - 3 Simulators", layout="wide", page_icon="🧪")

# --- ניהול שפה ב-Session State ---
if "lang" not in st.session_state:
    st.session_state.lang = "he"

def toggle_language():
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"

lang = st.session_state.lang
is_he = (lang == "he")

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

# --- תפריט ראשי עם 3 סימולטורים בדפים נפרדים לגמרי ---
UI = {
    "he": {
        "dir": "rtl", "align": "right",
        "nav_hdr": "תפריט מערכת ERP",
        "m_inv": "🗄️ מחסני מלאי (חומר גלם | בלקים | אריזות)",
        "m_sim_prod": "🧪 1. סימולטור קו ייצור (חו\"ג ⬅ בלקים)",
        "m_sim_pack": "📦 2. סימולטור אריזה (בלקים + אריזות)",
        "m_sim_work": "📊 3. סימולטור עבודה מסכם (הכל יחד)",
        "m_wh": "🔄 העברות בין מחסנים ורכש (SAP)",
        "m_ai": "🤖 סוכן פקודות מהיר",
        "lang_btn": "🌐 EN | English",
        "unit_lbl": "תצוגת משקל במערכת:",
        "kg": "ק\"ג (kg)", "g": "גרם (g)"
    },
    "en": {
        "dir": "ltr", "align": "left",
        "nav_hdr": "ERP Main Menu",
        "m_inv": "🗄️ Warehouses (Raw | Bulks | Packaging)",
        "m_sim_prod": "🧪 1. Production Line Simulator (Raw ⬅ Bulk)",
        "m_sim_pack": "📦 2. Packaging Simulator (Bulks + Pack)",
        "m_sim_work": "📊 3. Master Work Simulator (All Combined)",
        "m_wh": "🔄 Transfers & Purchase Orders (SAP)",
        "m_ai": "🤖 Quick Command Agent",
        "lang_btn": "🌐 עב | עברית",
        "unit_lbl": "System Weight Unit:",
        "kg": "kg", "g": "g"
    }
}[lang]

PLAN_PERIODS = [
    ("W1", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 1" if is_he else "Week 1"),
    ("W2", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 2" if is_he else "Week 2"),
    ("W3", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 3" if is_he else "Week 3"),
    ("W4", "נובמבר 2026" if is_he else "Nov 2026", "שבוע 4" if is_he else "Week 4"),
    ("W5", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 5" if is_he else "Week 5"),
    ("W6", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 6" if is_he else "Week 6"),
    ("W7", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 7" if is_he else "Week 7"),
    ("W8", "דצמבר 2026" if is_he else "Dec 2026", "שבוע 8" if is_he else "Week 8"),
]

# --- CSS מותאם ל-100% מרוחב המסך ללא גלילה אופקית ---
st.markdown(f"""
<style>
.stApp, .main, .block-container {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    font-family: 'Segoe UI', Tahoma, sans-serif;
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
}}
section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
a.header-anchor, [data-testid="stHeaderActionElements"] {{
    display: none !important;
}}
h1, h2, h3, h4, p, label, .stMarkdown {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
.clean-header {{
    background-color: var(--secondary-background-color);
    color: var(--text-color);
    border: 1px solid rgba(128,128,128,0.25);
    border-{"right" if is_he else "left"}: 5px solid #0284c7;
    padding: 12px 18px;
    border-radius: 10px;
    margin-bottom: 14px;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
div[data-testid="stMetric"] {{
    background-color: var(--secondary-background-color);
    color: var(--text-color);
    border: 1px solid rgba(128,128,128,0.22);
    padding: 10px 14px;
    border-radius: 10px;
}}
div[data-testid="stMetricLabel"] > div, div[data-testid="stMetricValue"] > div {{
    color: var(--text-color) !important;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] {{
    gap: 6px;
    direction: {UI['dir']} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
    background-color: var(--background-color);
    border: 1px solid rgba(128,128,128,0.22);
    border-radius: 8px;
    padding: 8px 12px !important;
    width: 100% !important;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
    border: 1.5px solid #0284c7 !important;
    background-color: rgba(2, 132, 199, 0.14);
    font-weight: 700 !important;
}}
.rtl-table {{
    width: 100% !important;
    table-layout: auto;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: right;
    margin: 8px 0 16px 0;
    font-size: 0.86rem;
}}
.rtl-table th, .rtl-table td {{
    border: 1px solid rgba(128,128,128,0.32);
    padding: 7px 8px;
    color: var(--text-color);
    text-align: right !important;
    word-wrap: break-word;
}}
.rtl-table th {{
    background-color: var(--secondary-background-color);
    font-weight: 700;
    border-top: 3px solid #0f4c5c;
}}
.matrix-table {{
    width: 100% !important;
    table-layout: fixed;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: center;
    margin: 8px 0 18px 0;
    font-size: 0.85rem;
}}
.matrix-table th, .matrix-table td {{
    border: 1px solid rgba(128,128,128,0.35);
    padding: 6px 4px;
    color: var(--text-color);
    word-wrap: break-word;
    overflow-wrap: break-word;
}}
.matrix-table thead tr:first-child th {{
    background-color: rgba(2, 132, 199, 0.18);
    font-weight: 700;
    font-size: 0.92rem;
}}
.matrix-table thead tr:nth-child(2) th {{
    background-color: var(--secondary-background-color);
    font-weight: 600;
    font-size: 0.82rem;
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
    font-size: 0.94rem;
    background: linear-gradient(135deg, rgba(2, 132, 199, 0.16) 0%, rgba(2, 132, 199, 0.05) 100%);
    border-left: 3px solid #0284c7 !important;
    padding: 8px 6px !important;
    line-height: 1.35;
}}
.matrix-table td.merged-stock-col {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    background-color: rgba(128, 128, 128, 0.08);
}}
.matrix-table tr.group-end td {{
    border-bottom: 2.5px solid rgba(2, 132, 199, 0.55) !important;
}}
.matrix-table td.stock-ok {{
    background-color: rgba(34, 197, 94, 0.22) !important;
    border: 1px solid rgba(34, 197, 94, 0.55) !important;
    padding: 6px 3px !important;
    vertical-align: middle;
}}
.matrix-table td.stock-short {{
    background-color: rgba(239, 68, 68, 0.26) !important;
    border: 1px solid rgba(239, 68, 68, 0.65) !important;
    padding: 6px 3px !important;
    vertical-align: middle;
}}
.matrix-table td.summary-ok {{
    background-color: rgba(34, 197, 94, 0.34) !important;
    border: 2px solid rgba(34, 197, 94, 0.8) !important;
    font-weight: 800;
    font-size: 0.95rem;
    vertical-align: middle !important;
}}
.matrix-table td.summary-short {{
    background-color: rgba(239, 68, 68, 0.38) !important;
    border: 2px solid rgba(239, 68, 68, 0.85) !important;
    font-weight: 800;
    font-size: 0.95rem;
    vertical-align: middle !important;
}}
.shared-badge {{
    display: inline-block;
    margin-top: 4px;
    padding: 2px 6px;
    border-radius: 999px;
    background-color: rgba(2, 132, 199, 0.22);
    border: 1px solid rgba(2, 132, 199, 0.55);
    font-size: 0.72rem;
    font-weight: 700;
}}
.cell-details {{
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
    font-size: 0.98rem;
    font-weight: 800;
    display: inline-block;
    padding: 1px 2px;
    border-radius: 4px;
    transition: transform 0.1s ease;
}}
.cell-details:hover .cell-main-val {{
    transform: scale(1.05);
    text-decoration: underline;
}}
.cell-breakdown-fit {{
    margin-top: 4px;
    padding: 4px 5px;
    border-radius: 6px;
    background-color: var(--background-color);
    border: 1px solid rgba(128,128,128,0.45);
    font-size: 0.74rem;
    font-weight: 600;
    text-align: {UI['align']};
    direction: {UI['dir']};
    line-height: 1.3;
    box-shadow: 0 2px 6px rgba(0,0,0,0.14);
}}
.legend-box {{
    display: flex;
    gap: 14px;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.88rem;
    flex-wrap: wrap;
}}
.legend-pill-ok {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    background-color: rgba(34, 197, 94, 0.22);
    border: 1px solid rgba(34, 197, 94, 0.6);
    font-weight: 700;
}}
.legend-pill-short {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 6px;
    background-color: rgba(239, 68, 68, 0.25);
    border: 1px solid rgba(239, 68, 68, 0.65);
    font-weight: 700;
}}
div.st-key-floating_lang_btn {{
    position: fixed !important;
    bottom: 18px !important;
    right: 22px !important;
    z-index: 999999 !important;
    width: auto !important;
}}
div.st-key-floating_lang_btn button {{
    background-color: #0284c7 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 999px !important;
    padding: 6px 16px !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.28) !important;
    cursor: pointer !important;
}}
</style>
""", unsafe_allow_html=True)

DB_NAME = "cosmetics_3sim_erp.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    # קטלוג מלא שכולל את כל השדות מהתרשים שלך:
    # מק"ט, שם פריט, מלאי, הזמנות פתוחות, תנועות מלאי, ספק, ספק חלופי, כניסות מלאי אחרונות
    c.execute("""CREATE TABLE IF NOT EXISTS Catalog (
        sku TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        item_type TEXT NOT NULL, -- 'RAW', 'BULK', 'PKG', 'FG'
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
    
    # עץ מוצר דו-שלבי:
    # שלב 1 (סימולטור קו ייצור): parent_sku = BULK, component_sku = RAW
    # שלב 2 (סימולטור אריזה): parent_sku = FG, component_sku = BULK / PKG
    c.execute("""CREATE TABLE IF NOT EXISTS BOM (
        parent_sku TEXT,
        component_sku TEXT,
        comp_type TEXT, -- 'RAW', 'BULK', 'PKG'
        req_qty_units REAL DEFAULT 0,
        req_weight_grams REAL DEFAULT 0,
        PRIMARY KEY (parent_sku, component_sku)
    )""")
    
    # תוכנית שבועות (עבור בלקים בקו הייצור ועבור מוצרים מוגמרים באריזה)
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

    c.execute("SELECT COUNT(*) FROM Catalog")
    if c.fetchone()[0] == 0:
        seed_items = [
            # 1. מחסן חומר גלם (RAW) - נמדד במשקל
            ("1001", "חמאת שיאה אורגנית / Shea Butter", "RAW", 0.0, 15000.0, "5 ק\"ג (PO-105)", "-1.2 ק\"ג לייצור", "נטורל אוילס", "בוטניקה סחר", "2026-11-10 (+10 ק\"ג)", 85.0, 5.0, 82.0, "WH_RAW", "SAP-1001"),
            ("1002", "שמן חוחובה טהור / Jojoba Oil", "RAW", 0.0, 9000.0, "0", "-0.8 ק\"ג לייצור", "נטורל אוילס", "גליל אוילס", "2026-11-08 (+5 ק\"ג)", 140.0, 3.0, 138.0, "WH_RAW", "SAP-1002"),
            ("1003", "חומצה היאלורונית / Hyaluronic Acid", "RAW", 0.0, 800.0, "5 ק\"ג (PO-101)", "-0.3 ק\"ג לייצור", "כימדע", "פארמה-כם", "2026-11-01 (+1 ק\"ג)", 1200.0, 1.0, 1150.0, "WH_RAW", "SAP-1003"),
            ("1004", "בסיס אמולסיה לקרם / Cream Base", "RAW", 0.0, 25000.0, "0", "-3.5 ק\"ג לייצור", "בוטניקה סחר", "כימדע", "2026-11-12 (+20 ק\"ג)", 45.0, 10.0, 42.0, "WH_RAW", "SAP-1004"),
            
            # 2. מחסן בלקים (BULK) - התוצר של קו הייצור שנכנס למחסן בלקים ונמדד במשקל
            ("2001", "בלק קרם פנים היאלורוני (מוכן למילוי)", "BULK", 0.0, 6000.0, "אצווה #402 (10 ק\"ג)", "+6 ק\"ג מקו ייצור", "קו ייצור פנימי", "-", "2026-11-14 (+6 ק\"ג)", 160.0, 5.0, 155.0, "WH_BULK", "SAP-2001"),
            ("2002", "בלק סרום הזנה חוחובה (מוכן למילוי)", "BULK", 0.0, 3500.0, "אצווה #403 (5 ק\"ג)", "+3.5 ק\"ג מקו ייצור", "קו ייצור פנימי", "-", "2026-11-13 (+3.5 ק\"ג)", 210.0, 5.0, 200.0, "WH_BULK", "SAP-2002"),
            
            # 3. מחסן אריזות (PKG) - בקבוקים, צנצנות, מכסים, מתזים, מדבקות - נמדד ביחידות
            ("3001", "צנצנת זכוכית 50ml לקרם", "PKG", 1200.0, 0.0, "1000 יח' (PO-204)", "-200 יח' לאריזה", "אריזות המרכז", "גלאס-פק", "2026-11-05 (+1500 יח')", 2.2, 500.0, 2.1, "WH_PACK", "SAP-3001"),
            ("3002", "מכסה מוזהב לצנצנת 50ml", "PKG", 950.0, 0.0, "0", "-200 יח' לאריזה", "אריזות המרכז", "גלאס-פק", "2026-11-05 (+1000 יח')", 0.8, 500.0, 0.75, "WH_PACK", "SAP-3002"),
            ("3003", "בקבוק זכוכית 30ml לסרום", "PKG", 850.0, 0.0, "500 יח'", "-150 יח' לאריזה", "אריזות המרכז", "אקו-בוטל", "2026-11-06 (+1000 יח')", 2.0, 500.0, 1.9, "WH_PACK", "SAP-3003"),
            ("3004", "מתז / טפטפת לסרום 30ml", "PKG", 600.0, 0.0, "1000 יח'", "-150 יח' לאריזה", "אריזות המרכז", "אקו-בוטל", "2026-11-06 (+800 יח')", 1.2, 500.0, 1.1, "WH_PACK", "SAP-3004"),
            ("3005", "מדבקת חזית וברקוד (משותפת)", "PKG", 1800.0, 0.0, "2000 יח'", "-350 יח' לאריזה", "דפוס מדבקות", "פרינט-פרו", "2026-11-09 (+2000 יח')", 0.4, 1000.0, 0.38, "WH_PACK", "SAP-3005"),
            
            # 4. מוצרים מוגמרים ארוזים (FG)
            ("5001", "קרם פנים היאלורוני 50ml ארוז", "FG", 60.0, 0.0, "0", "+60 יח' מאריזה", "מחלקת אריזה", "-", "2026-11-14 (+60 יח')", 45.0, 50.0, 32.0, "WH_FG", "SAP-5001"),
            ("5002", "סרום הזנה חוחובה 30ml ארוז", "FG", 40.0, 0.0, "0", "+40 יח' מאריזה", "מחלקת אריזה", "-", "2026-11-14 (+40 יח')", 55.0, 50.0, 38.0, "WH_FG", "SAP-5002")
        ]
        c.executemany("INSERT INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", seed_items)
            
        seed_bom = [
            # עץ מוצר לסימולטור קו ייצור: ייצור 1 ק"ג (1000 גרם) של בלק מתוך מחסן חומרי גלם (RAW -> BULK)
            # עבור 1 ק"ג של בלק קרם פנים (2001): 700 גרם בסיס אמולסיה, 200 גרם חמאת שיאה, 100 גרם חומצה היאלורונית
            ("2001", "1004", "RAW", 0.0, 700.0),
            ("2001", "1001", "RAW", 0.0, 200.0),
            ("2001", "1003", "RAW", 0.0, 100.0),
            # עבור 1 ק"ג של בלק סרום (2002): 900 גרם שמן חוחובה, 100 גרם חומצה היאלורונית (משותפת!)
            ("2002", "1002", "RAW", 0.0, 900.0),
            ("2002", "1003", "RAW", 0.0, 100.0),

            # עץ מוצר לסימולטור אריזה: אריזת יחידת מוצר סופי 1 מתוך מחסן בלקים + מחסן אריזות (BULK + PKG -> FG)
            # יחידה 1 של קרם פנים 50ml ארוז (5001): דורשת 50 גרם בלק קרם (2001) + 1 צנצנת (3001) + 1 מכסה (3002) + 1 מדבקה (3005)
            ("5001", "2001", "BULK", 0.0, 50.0),
            ("5001", "3001", "PKG", 1.0, 0.0),
            ("5001", "3002", "PKG", 1.0, 0.0),
            ("5001", "3005", "PKG", 1.0, 0.0),
            # יחידה 1 של סרום 30ml ארוז (5002): דורשת 30 גרם בלק סרום (2002) + 1 בקבוק (3003) + 1 מתז (3004) + 1 מדבקה (3005)
            ("5002", "2002", "BULK", 0.0, 30.0),
            ("5002", "3003", "PKG", 1.0, 0.0),
            ("5002", "3004", "PKG", 1.0, 0.0),
            ("5002", "3005", "PKG", 1.0, 0.0)
        ]
        c.executemany("INSERT INTO BOM VALUES (?,?,?,?,?)", seed_bom)
        
        # תוכנית ייצור לבלקים (בק"ג בלק לשבוע) ותוכנית אריזה למוצרים (ביחידות לשבוע)
        c.execute("INSERT INTO WeeklySchedule VALUES ('2001', 6, 8, 5, 10, 8, 7, 10, 6)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('2002', 3, 4, 4, 3, 5, 4, 3, 5)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('5001', 120, 150, 100, 200, 180, 160, 220, 140)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('5002', 80, 100, 120, 90, 110, 130, 100, 150)")
        
        today = datetime.today()
        c.execute("""
            INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("PO-101", "1003", "כימדע", 0.0, 5000.0, 1180.0, today.strftime("%Y-%m-%d"), (today + timedelta(days=5)).strftime("%Y-%m-%d"), "WH_RAW", "In Transit"))
        conn.commit()
    conn.close()

init_db()
conn = get_connection()

# --- סרגל צד עם 3 סימולטורים בדפים נפרדים ---
st.sidebar.markdown(f"### 🧪 {UI['nav_hdr']}")
menu = st.sidebar.radio(
    "Nav",
    [
        UI["m_inv"],
        UI["m_sim_prod"],
        UI["m_sim_pack"],
        UI["m_sim_work"],
        UI["m_wh"],
        UI["m_ai"]
    ],
    label_visibility="collapsed"
)

st.sidebar.divider()
w_choice = st.sidebar.radio(UI["unit_lbl"], [UI["kg"], UI["g"]], index=0, horizontal=True)
use_kg = (w_choice == UI["kg"])
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

# --- כפתור שפה צף בפינה הימנית התחתונה ---
st.button(UI["lang_btn"], on_click=toggle_language, key="floating_lang_btn")

# --- פונקציית עזר לרינדור טבלת סימולטור Where-Used (מק"ט בן מימין ומק"טי אב משויכים) ---
def render_where_used_simulator(df_sched_sub, df_bom_sub, parent_unit_str):
    week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    month1_name = PLAN_PERIODS[0][1]
    month2_name = PLAN_PERIODS[4][1]

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
                "after_bal": after_bal
            }

    final_comp_balance = {}
    for c_sku, grp in df_bom_sub.groupby("component_sku", sort=False):
        last_row_idx = grp.index[-1]
        final_comp_balance[c_sku] = cell_status[(last_row_idx, "W8")]

    # סרגל חיפוש לפי מק"ט בן או מק"ט אב
    all_lbl = "הכל" if is_he else "All"
    child_opts = [all_lbl] + list((df_bom_sub["component_sku"] + " - " + df_bom_sub["comp_name"]).unique())
    parent_opts = [all_lbl] + list((df_sched_sub["sku"] + " - " + df_sched_sub["parent_name"]).unique())

    s1, s2, s3 = st.columns([2, 1.5, 1.5])
    with s1:
        q_search = st.text_input("🔍 חיפוש לפי מק\"ט בן או מק\"ט אב:" if is_he else "🔍 Search Child or Parent SKU:")
    with s2:
        sel_c = st.selectbox("סנן לפי מק\"ט בן:" if is_he else "Filter Child SKU:", child_opts)
    with s3:
        sel_p = st.selectbox("סנן לפי מק\"ט אב משויך:" if is_he else "Filter Linked Parent:", parent_opts)

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

    # טבלה 1: תוכנית ייצור/אריזה שבועית למק"טי האב
    rows_sched_html = ""
    for _, row in df_sched_sub.iterrows():
        tot_p = int(row["W1"] + row["W2"] + row["W3"] + row["W4"] + row["W5"] + row["W6"] + row["W7"] + row["W8"])
        rows_sched_html += (
            f"<tr>"
            f"<td class='parent-col'>{row['parent_label']}</td>"
            f"<td>{int(row['W1'])} {parent_unit_str}</td><td>{int(row['W2'])} {parent_unit_str}</td><td>{int(row['W3'])} {parent_unit_str}</td><td>{int(row['W4'])} {parent_unit_str}</td>"
            f"<td>{int(row['W5'])} {parent_unit_str}</td><td>{int(row['W6'])} {parent_unit_str}</td><td>{int(row['W7'])} {parent_unit_str}</td><td>{int(row['W8'])} {parent_unit_str}</td>"
            f"<td><b>{tot_p:,} {parent_unit_str}</b></td>"
            f"</tr>"
        )

    st.markdown(
        f"<table class='matrix-table'><thead>"
        f"<tr><th rowspan='2' style='width:18%; text-align:right;'>{'מק\"ט אב ותוכנית שבועית' if is_he else 'Parent SKU Schedule'}</th>"
        f"<th colspan='4' style='width:37%;'>{month1_name}</th><th colspan='4' style='width:37%;'>{month2_name}</th>"
        f"<th rowspan='2' style='width:8%;'>{'סה\"כ' if is_he else 'Total'}</th></tr>"
        f"<tr><th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th></tr>"
        f"</thead><tbody>{rows_sched_html}</tbody></table>",
        unsafe_allow_html=True
    )

    with st.expander("✏️ עריכת כמויות שבועות" if is_he else "✏️ Edit Weekly Quantities", expanded=False):
        ed_s = st.data_editor(
            df_sched_sub[["W8", "W7", "W6", "W5", "W4", "W3", "W2", "W1", "parent_label"]],
            use_container_width=True, hide_index=True
        )
        if st.button("💾 שמור תוכנית שבועות" if is_he else "💾 Save Weekly Plan"):
            for _, r in ed_s.iterrows():
                p_sku = r["parent_label"].split(" - ")[0]
                conn.execute("UPDATE WeeklySchedule SET W1=?,W2=?,W3=?,W4=?,W5=?,W6=?,W7=?,W8=? WHERE parent_sku=?",
                             (r["W1"], r["W2"], r["W3"], r["W4"], r["W5"], r["W6"], r["W7"], r["W8"], p_sku))
            conn.commit()
            st.rerun()

    # טבלה 2: טבלת סימולציית המלאי (מק"ט בן מימין + מק"טי אב משויכים + צבירת חוסרים)
    rows_bom_html = ""
    for comp_sku, group in df_bom_view.groupby("component_sku", sort=False):
        span_count = len(group)
        is_shared = (span_count > 1)
        for idx_in_group, (row_idx, r) in enumerate(group.iterrows()):
            is_w = (r["comp_type"] in ["RAW", "BULK"])
            per_unit_base = float(r["req_weight_grams"] if is_w else r["req_qty_units"])
            initial_stock_base = float(r["avail_grams"] if is_w else r["avail_units"])
            is_last_in_group = (idx_in_group == span_count - 1)
            tr_class = " class='group-end'" if is_last_in_group else ""

            child_td = ""
            init_stock_td = ""
            final_sum_td = ""

            if idx_in_group == 0:
                shared_tag = (
                    f"<span class='shared-badge'>🔗 {'משותף ל-' + str(span_count) + ' מק\"טי אב' if is_he else 'Shared by ' + str(span_count)}</span>"
                    if is_shared else ""
                )
                child_td = (
                    f"<td class='merged-child-col' rowspan='{span_count}'>"
                    f"<div>{r['component_sku']}</div>"
                    f"<div style='font-size:0.82rem; font-weight:600; opacity:0.9;'>{r['comp_name']}</div>"
                    f"{shared_tag}"
                    f"</td>"
                )
                init_stock_td = f"<td class='merged-stock-col' rowspan='{span_count}'>{fmt_val(initial_stock_base, is_w)}</td>"
                fin_info = final_comp_balance[comp_sku]
                fin_str = fmt_val(fin_info["after_bal"], is_w)
                sum_cls = "summary-ok" if fin_info["is_ok"] else "summary-short"
                final_sum_td = f"<td class='{sum_cls}' rowspan='{span_count}'>{fin_str}</td>"

            week_tds_html = ""
            for w_col in week_cols:
                st_info = cell_status[(row_idx, w_col)]
                before_str = fmt_val(st_info["before_bal"], is_w)
                used_parent_str = fmt_val(st_info["used_parent"], is_w)
                tot_used_str = fmt_val(st_info["tot_used_all_parents"], is_w)
                after_str = fmt_val(st_info["after_bal"], is_w)

                shared_line = f"סה\"כ כל האבות: <b>{tot_used_str}</b><br>" if (is_shared and is_he) else ""
                if is_he:
                    breakdown_html = (
                        f"<div class='cell-breakdown-fit'>"
                        f"לפני: <b>{before_str}</b><br>"
                        f"שימוש ל-{r['parent_sku']}: <b>{used_parent_str}</b><br>"
                        f"{shared_line}"
                        f"{'נשאר במלאי' if st_info['is_ok'] else '<span style=\"color:#ef4444;\">חוסר מצטבר</span>'}: <b>{after_str}</b>"
                        f"</div>"
                    )
                else:
                    breakdown_html = (
                        f"<div class='cell-breakdown-fit'>"
                        f"Before: <b>{before_str}</b><br>"
                        f"Used ({r['parent_sku']}): <b>{used_parent_str}</b><br>"
                        f"Balance: <b>{after_str}</b>"
                        f"</div>"
                    )

                td_cls = "stock-ok" if st_info["is_ok"] else "stock-short"
                week_tds_html += (
                    f"<td class='{td_cls}'>"
                    f"<details class='cell-details'>"
                    f"<summary><span class='cell-main-val'>{after_str}</span></summary>"
                    f"{breakdown_html}"
                    f"</details>"
                    f"</td>"
                )

            rows_bom_html += (
                f"<tr{tr_class}>"
                f"{child_td}"
                f"<td style='text-align:right;'><b>{r['parent_sku']}</b> - {r['parent_name']}</td>"
                f"<td><b>{fmt_val(per_unit_base, is_w)}</b></td>"
                f"{init_stock_td}"
                f"{week_tds_html}"
                f"{final_sum_td}"
                f"</tr>"
            )

    st.markdown(
        f"<table class='matrix-table'><thead>"
        f"<tr>"
        f"<th rowspan='2' style='width:14%; text-align:center;'>{'מק\"ט בן (במחסן)' if is_he else 'Child SKU'}</th>"
        f"<th rowspan='2' style='width:14%; text-align:right;'>{'מק\"ט אב משויך' if is_he else 'Linked Parent'}</th>"
        f"<th rowspan='2' style='width:6%;'>{'ליחידת אב' if is_he else 'Per 1'}</th>"
        f"<th rowspan='2' style='width:8%;'>{'מלאי קיים במחסן' if is_he else 'Current Stock'}</th>"
        f"<th colspan='4' style='width:24.5%;'>{month1_name}</th><th colspan='4' style='width:24.5%;'>{month2_name}</th>"
        f"<th rowspan='2' style='width:9%;'>{'סה\"כ מאזן / חוסר מצטבר' if is_he else 'Cum. Balance'}</th>"
        f"</tr><tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead><tbody>{rows_bom_html}</tbody></table>",
        unsafe_allow_html=True
    )

# ==============================================================================
# דף 1: מחסני המלאי לפי התרשים (חומר גלם | בלקים | אריזות)
# ==============================================================================
if menu == UI["m_inv"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_inv"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)

    # 3 כרטיסי סיכום עבור 3 המחסנים שבתרשים שלך
    c1, c2, c3 = st.columns(3)
    raw_tot = fmt_val(df_cat[df_cat["item_type"] == "RAW"]["weight_grams"].sum(), True)
    bulk_tot = fmt_val(df_cat[df_cat["item_type"] == "BULK"]["weight_grams"].sum(), True)
    pkg_tot = fmt_val(df_cat[df_cat["item_type"] == "PKG"]["qty_units"].sum(), False)

    c1.metric("🧪 מחסן חומר גלם (RAW)" if is_he else "Raw Materials WH", raw_tot)
    c2.metric("🛢️ מחסן בלקים - חומר מוכן (BULK)" if is_he else "Bulks WH", bulk_tot)
    c3.metric("📦 מחסן אריזות (בקבוקים/מכסים/מתזים/מדבקות)" if is_he else "Packaging WH", pkg_tot)

    t_raw, t_bulk, t_pkg, t_edit = st.tabs([
        "🧪 1. טבלת מחסן חומר גלם" if is_he else "1. Raw Materials WH",
        "🛢️ 2. טבלת מחסן בלקים (חומר שהוכן)" if is_he else "2. Bulks WH",
        "📦 3. טבלת מחסן אריזות" if is_he else "3. Packaging WH",
        "✏️ עריכה / הוספת פריטים למחסנים" if is_he else "✏️ Edit / Add Items"
    ])

    def render_schema_table(df_subset, is_weight_table):
        rows_h = ""
        for _, r in df_subset.iterrows():
            stock_str = fmt_val(r["weight_grams"] if is_weight_table else r["qty_units"], is_weight_table)
            rows_h += (
                f"<tr>"
                f"<td><b>{r['sku']}</b></td>"
                f"<td><b>{r['name']}</b></td>"
                f"<td><b>{stock_str}</b></td>"
                f"<td>{r['open_orders']}</td>"
                f"<td>{r['stock_movements']}</td>"
                f"<td>{r['main_supplier']}</td>"
                f"<td>{r['alt_suppliers']}</td>"
                f"<td>{r['last_stock_entry']}</td>"
                f"</tr>"
            )
        tbl_h = (
            f"<table class='rtl-table'><thead><tr>"
            f"<th>🔑 מק\"ט</th>"
            f"<th>שם פריט</th>"
            f"<th>מלאי ({w_label if is_weight_table else u_label})</th>"
            f"<th>הזמנות פתוחות</th>"
            f"<th>תנועות מלאי</th>"
            f"<th>ספק</th>"
            f"<th>ספק חלופי</th>"
            f"<th>כניסות מלאי אחרונות</th>"
            f"</tr></thead><tbody>{rows_h}</tbody></table>"
        )
        st.markdown(tbl_h, unsafe_allow_html=True)

    with t_raw:
        st.subheader("חומר גלם (נמדד במשקל בלבד - מזין את סימולטור קו הייצור)")
        render_schema_table(df_cat[df_cat["item_type"] == "RAW"], True)

    with t_bulk:
        st.subheader("בלקים - חומר מבושל מוכן (מגיע מקו הייצור ומזין את סימולטור האריזה)")
        render_schema_table(df_cat[df_cat["item_type"] == "BULK"], True)

    with t_pkg:
        st.subheader("אריזות - בקבוקים, צנצנות, מכסים, מתזים ומדבקות (נמדד ביח' - מזין את סימולטור האריזה)")
        render_schema_table(df_cat[df_cat["item_type"] == "PKG"], False)

    with t_edit:
        df_ed = df_cat.copy()
        df_ed["stock_val"] = df_ed.apply(
            lambda r: round(r["weight_grams"] / w_factor, 3) if r["item_type"] in ["RAW", "BULK"] else round(r["qty_units"], 0),
            axis=1
        )
        edited_cat = st.data_editor(
            df_ed[["last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements", "open_orders", "stock_val", "item_type", "name", "sku"]],
            column_config={
                "sku": st.column_config.TextColumn("🔑 מק\"ט", required=True),
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
        if st.button("💾 שמור שינויים בכל המחסנים"):
            conn.execute("DELETE FROM Catalog")
            for _, r in edited_cat.iterrows():
                if pd.notna(r["sku"]) and str(r["sku"]).strip():
                    tp = str(r["item_type"] or "RAW")
                    v_num = float(r["stock_val"] or 0)
                    w_g = (v_num * w_factor) if tp in ["RAW", "BULK"] else 0.0
                    q_u = 0.0 if tp in ["RAW", "BULK"] else v_num
                    wh_k = "WH_RAW" if tp == "RAW" else ("WH_BULK" if tp == "BULK" else ("WH_PACK" if tp == "PKG" else "WH_FG"))
                    conn.execute("""
                        INSERT INTO Catalog (sku, name, item_type, qty_units, weight_grams, open_orders, stock_movements, main_supplier, alt_suppliers, last_stock_entry, primary_warehouse)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                    """, (str(r["sku"]).strip(), str(r["name"]), tp, q_u, w_g, str(r["open_orders"] or "0"),
                          str(r["stock_movements"] or "-"), str(r["main_supplier"] or ""), str(r["alt_suppliers"] or ""),
                          str(r["last_stock_entry"] or "-"), wh_k))
            conn.commit()
            st.success("המחסנים עודכנו בהצלחה!")
            st.rerun()

# ==============================================================================
# דף 2 (סימולטור 1): 🧪 סימולטור קו ייצור (שואב רק ממחסן חומרי גלם -> מעביר למחסן בלקים)
# ==============================================================================
elif menu == UI["m_sim_prod"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_prod"]}</h2></div>', unsafe_allow_html=True)
    st.info("🧪 **סימולטור קו ייצור:** לוקח מידע **אך ורק ממחסן חומרי גלם (`RAW`)**, בודק היתכנות בישול/ייצור של **בלקים**, ובלחיצת כפתור מעביר את החומר המוכן אל **מחסן בלקים (`BULK`)**.")

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

    render_where_used_simulator(df_sched_prod, df_bom_prod, "ק\"ג בלק" if is_he else "kg Bulk")

    st.divider()
    st.subheader("⚙️ ביצוע ייצור בקו והעברת המוצר המוכן למחסן בלקים")
    cp1, cp2 = st.columns(2)
    with cp1:
        sel_bulk_make = st.selectbox("בחר בלק לייצור בקו:", bulk_df["sku"] + " - " + bulk_df["name"])
    with cp2:
        kg_to_make = st.number_input("כמות בלק לייצור (בק\"ג):", min_value=1.0, value=10.0, step=1.0)

    if st.button("🚀 ייצר בלק עכשיו (גרע ממחסן חומרי גלם והעבר למחסן בלקים)"):
        b_sku = sel_bulk_make.split(" - ")[0]
        bom_rows = pd.read_sql("SELECT component_sku, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(b_sku,))
        now_d = datetime.now().strftime("%Y-%m-%d")
        for _, br in bom_rows.iterrows():
            consume_g = float(br["req_weight_grams"]) * kg_to_make
            conn.execute("""
                UPDATE Catalog
                SET weight_grams = MAX(0, weight_grams - ?),
                    stock_movements = ?
                WHERE sku = ?
            """, (consume_g, f"-{consume_g/1000:.2f} ק\"ג לבלק {b_sku}", br["component_sku"]))

        produced_g = kg_to_make * 1000.0
        conn.execute("""
            UPDATE Catalog
            SET weight_grams = weight_grams + ?,
                stock_movements = ?,
                last_stock_entry = ?
            WHERE sku = ?
        """, (produced_g, f"+{kg_to_make:.1f} ק\"ג מקו ייצור", f"{now_d} (+{kg_to_make:.1f} ק\"ג)", b_sku))
        conn.commit()
        st.success(f"יוצרו {kg_to_make} ק\"ג של בלק {b_sku}! חומרי הגלם נגרעו, והבלק הועבר למחסן בלקים.")
        st.rerun()

# ==============================================================================
# דף 3 (סימולטור 2): 📦 סימולטור אריזה (שואב רק ממחסן בלקים + מחסן אריזות)
# ==============================================================================
elif menu == UI["m_sim_pack"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_pack"]}</h2></div>', unsafe_allow_html=True)
    st.info("📦 **סימולטור אריזה:** לוקח מידע **אך ורק ממחסן בלקים (`BULK`) וממחסן אריזות (`PKG` - בקבוקים, מכסים, מתזים, מדבקות)** ובודק כמה יחידות מוצר סופי ניתן למלא ולארוז.")

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
        SELECT b.component_sku, c.name AS comp_name, b.comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        WHERE p.item_type = 'FG' AND c.item_type IN ('BULK', 'PKG')
        ORDER BY b.comp_type, b.component_sku, b.parent_sku
    """, conn)

    render_where_used_simulator(df_sched_pack, df_bom_pack, u_label)

    st.divider()
    st.subheader("📦 ביצוע פעולת מילוי ואריזה (גריעה ממחסן בלקים וממחסן אריזות)")
    ck1, ck2 = st.columns(2)
    with ck1:
        sel_fg_pack = st.selectbox("בחר מוצר סופי לאריזה:", fg_df["sku"] + " - " + fg_df["name"])
    with ck2:
        units_to_pack = st.number_input("כמות יחידות למילוי ואריזה:", min_value=1, value=100, step=10)

    if st.button("✅ בצע אריזה (גרע בלק ממחסן בלקים + בקבוקים/מכסים/מדבקות ממחסן אריזות)"):
        f_sku = sel_fg_pack.split(" - ")[0]
        bom_p = pd.read_sql("SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?", conn, params=(f_sku,))
        now_d = datetime.now().strftime("%Y-%m-%d")
        for _, br in bom_p.iterrows():
            if br["comp_type"] == "BULK":
                use_g = float(br["req_weight_grams"]) * units_to_pack
                conn.execute("UPDATE Catalog SET weight_grams = MAX(0, weight_grams - ?), stock_movements = ? WHERE sku = ?",
                             (use_g, f"-{use_g/1000:.2f} ק\"ג לאריזת {f_sku}", br["component_sku"]))
            else:
                use_u = float(br["req_qty_units"]) * units_to_pack
                conn.execute("UPDATE Catalog SET qty_units = MAX(0, qty_units - ?), stock_movements = ? WHERE sku = ?",
                             (use_u, f"-{use_u:.0f} יח' לאריזת {f_sku}", br["component_sku"]))
        conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku = ?",
                     (units_to_pack, f"{now_d} (+{units_to_pack} יח')", f_sku))
        conn.commit()
        st.success(f"נארזו {units_to_pack} יח' של {f_sku}! המלאי נגרע ממחסן הבלקים וממחסן האריזות.")
        st.rerun()

# ==============================================================================
# דף 4 (סימולטור 3): 📊 סימולטור עבודה מסכם (סוכם הכל יחד: כמה אפשר להכין בפועל + מה חסר וכמה חסר)
# ==============================================================================
elif menu == UI["m_sim_work"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_sim_work"]}</h2></div>', unsafe_allow_html=True)
    st.info("📊 **סימולטור עבודה מסכם:** משלב את **מחסן חומרי הגלם + מחסן הבלקים + מחסן האריזות** יחד, ומציג בקיצור כמה יחידות ניתן להכין בפועל, מה בדיוק חסר וכמה חסר ממנו.")

    fg_df = pd.read_sql("SELECT * FROM Catalog WHERE item_type = 'FG'", conn)
    cat_all = pd.read_sql("SELECT * FROM Catalog", conn).set_index("sku")
    bom_all = pd.read_sql("SELECT * FROM BOM", conn)

    # בחירת יעד ייצור כולל לבדיקה בסימולטור העבודה
    st.subheader("1. הגדרת כמות יעד לבדיקה כוללת (או לפי סך תוכנית השבועות)")
    target_inputs = {}
    cols_t = st.columns(max(1, len(fg_df)))
    for idx, (_, fg_row) in enumerate(fg_df.iterrows()):
        sched_row = pd.read_sql("SELECT W1+W2+W3+W4+W5+W6+W7+W8 AS tot FROM WeeklySchedule WHERE parent_sku=?", conn, params=(fg_row["sku"],))
        default_tot = int(sched_row["tot"].iloc[0]) if not sched_row.empty else 500
        with cols_t[idx]:
            target_inputs[fg_row["sku"]] = st.number_input(
                f"יעד יחידות כולל: {fg_row['sku']} - {fg_row['name']}",
                min_value=1, value=default_tot, step=50
            )

    # חישוב 1: כמה ניתן להכין בפועל עבור כל מוצר סופי (לפי בלק קיים + לפי בלק שניתן לבשל מחו"ג + לפי אריזות)
    summary_cards_html = ""
    exec_rows = []
    for _, fg_row in fg_df.iterrows():
        f_sku = fg_row["sku"]
        target_u = target_inputs[f_sku]
        sub_bom = bom_all[bom_all["parent_sku"] == f_sku]

        max_by_existing_bulk = 999999
        max_by_raw_to_bulk = 999999
        max_by_packaging = 999999
        limiting_item_name = "-"

        for _, b_r in sub_bom.iterrows():
            c_sku = b_r["component_sku"]
            if c_sku not in cat_all.index:
                continue
            comp_item = cat_all.loc[c_sku]

            if b_r["comp_type"] == "BULK":
                req_g_per_unit = float(b_r["req_weight_grams"])
                existing_bulk_g = float(comp_item["weight_grams"])
                possible_from_bulk = int(existing_bulk_g // req_g_per_unit) if req_g_per_unit > 0 else 999999

                # כמה בלק נוסף אפשר לייצר מחומרי הגלם שבמחסן חו"ג
                raw_bom = bom_all[bom_all["parent_sku"] == c_sku]
                max_extra_bulk_kg = 999999.0
                for _, rb in raw_bom.iterrows():
                    r_sku = rb["component_sku"]
                    if r_sku in cat_all.index:
                        raw_avail_g = float(cat_all.loc[r_sku]["weight_grams"])
                        req_raw_per_kg_bulk = float(rb["req_weight_grams"])
                        if req_raw_per_kg_bulk > 0:
                            max_extra_bulk_kg = min(max_extra_bulk_kg, raw_avail_g / req_raw_per_kg_bulk)

                extra_bulk_g = (max_extra_bulk_kg * 1000.0) if max_extra_bulk_kg < 999999.0 else 0.0
                possible_total_bulk = int((existing_bulk_g + extra_bulk_g) // req_g_per_unit) if req_g_per_unit > 0 else 999999

                if possible_from_bulk < max_by_existing_bulk:
                    max_by_existing_bulk = possible_from_bulk
                if possible_total_bulk < max_by_raw_to_bulk:
                    max_by_raw_to_bulk = possible_total_bulk
            else:
                req_u_per_unit = float(b_r["req_qty_units"])
                avail_u = float(comp_item["qty_units"])
                possible_pkg = int(avail_u // req_u_per_unit) if req_u_per_unit > 0 else 999999
                if possible_pkg < max_by_packaging:
                    max_by_packaging = possible_pkg
                    limiting_item_name = f"{c_sku} ({comp_item['name']})"

        can_make_immediately = min(max_by_existing_bulk, max_by_packaging)
        can_make_with_cooking = min(max_by_raw_to_bulk, max_by_packaging)
        missing_for_target = max(0, target_u - can_make_with_cooking)

        exec_rows.append(
            f"<tr>"
            f"<td><b>{f_sku} - {fg_row['name']}</b></td>"
            f"<td><b>{target_u:,} {u_label}</b></td>"
            f"<td class='stock-ok'><b>{can_make_immediately:,} {u_label}</b> (מבלק קיים במחסן)</td>"
            f"<td class='stock-ok'><b>{can_make_with_cooking:,} {u_label}</b> (כולל בישול חו\"ג לבלק)</td>"
            f"<td class='{'stock-short' if missing_for_target > 0 else 'stock-ok'}'>"
            f"{'<span dir=\"ltr\">-' + f'{missing_for_target:,}' + '</span> ' + u_label if missing_for_target > 0 else '0 (יש הכל!)'}"
            f"</td>"
            f"<td>{limiting_item_name}</td>"
            f"</tr>"
        )

    st.subheader("2. סיכום מנהלים: כמה ניתן להכין בפועל מכל מוצר")
    st.markdown(
        f"<table class='rtl-table'><thead><tr>"
        f"<th>מוצר סופי</th>"
        f"<th>כמות יעד מבוקשת</th>"
        f"<th>ניתן לארוז מיידית (מבלק קיים + אריזות)</th>"
        f"<th>ניתן להכין סה\"כ (כולל ייצור בלק מחו\"ג)</th>"
        f"<th>יחידות מוצר שחסרות ליעד</th>"
        f"<th>רכיב אריזה מגביל (צוואר בקבוק)</th>"
        f"</tr></thead><tbody>{''.join(exec_rows)}</tbody></table>",
        unsafe_allow_html=True
    )

    # חישוב 2: טבלה מרוכזת של כל הפריטים בכל 3 המחסנים - מה יש, כמה צריך סה"כ, ומה חסר במינוס
    st.subheader("3. פירוט חוסרים מרוכז בכל המחסנים (מה חסר לי וכמה חסר ממנו)")

    # דרישות אריזות ובלקים עבור כל המוצרים יחד
    total_pkg_req = {}
    total_bulk_req_grams = {}

    for f_sku, t_qty in target_inputs.items():
        sub_b = bom_all[bom_all["parent_sku"] == f_sku]
        for _, br in sub_b.iterrows():
            c_sku = br["component_sku"]
            if br["comp_type"] == "BULK":
                total_bulk_req_grams[c_sku] = total_bulk_req_grams.get(c_sku, 0.0) + (t_qty * float(br["req_weight_grams"]))
            else:
                total_pkg_req[c_sku] = total_pkg_req.get(c_sku, 0.0) + (t_qty * float(br["req_qty_units"]))

    # גזירת דרישות חומרי גלם עבור כמות הבלק שחסרה במחסן בלקים
    total_raw_req_grams = {}
    for b_sku, req_b_grams in total_bulk_req_grams.items():
        avail_b_grams = float(cat_all.loc[b_sku]["weight_grams"]) if b_sku in cat_all.index else 0.0
        net_bulk_to_produce_kg = max(0.0, (req_b_grams - avail_b_grams) / 1000.0)
        raw_sub = bom_all[bom_all["parent_sku"] == b_sku]
        for _, rb in raw_sub.iterrows():
            r_sku = rb["component_sku"]
            total_raw_req_grams[r_sku] = total_raw_req_grams.get(r_sku, 0.0) + (net_bulk_to_produce_kg * float(rb["req_weight_grams"]))

    shortage_rows_html = ""
    for sku_id, item_r in cat_all.iterrows():
        tp = item_r["item_type"]
        if tp == "FG":
            continue
        is_w = (tp in ["RAW", "BULK"])
        avail_val = float(item_r["weight_grams"] if is_w else item_r["qty_units"])
        if tp == "RAW":
            req_val = total_raw_req_grams.get(sku_id, 0.0)
        elif tp == "BULK":
            req_val = total_bulk_req_grams.get(sku_id, 0.0)
        else:
            req_val = total_pkg_req.get(sku_id, 0.0)

        diff_val = avail_val - req_val
        is_ok = (diff_val >= -1e-6)
        cls_td = "stock-ok" if is_ok else "stock-short"

        shortage_rows_html += (
            f"<tr>"
            f"<td><b>{sku_id}</b></td>"
            f"<td>{item_r['name']}</td>"
            f"<td><b>{tr_type(tp)}</b></td>"
            f"<td>{fmt_val(avail_val, is_w)}</td>"
            f"<td>{fmt_val(req_val, is_w)}</td>"
            f"<td class='{cls_td}' style='text-align:center !important;'><b>{fmt_val(diff_val, is_w)}</b></td>"
            f"<td>{item_r['open_orders']}</td>"
            f"<td>{item_r['main_supplier']} ({item_r['alt_suppliers']})</td>"
            f"</tr>"
        )

    st.markdown(
        f"<table class='rtl-table'><thead><tr>"
        f"<th>מק\"ט</th>"
        f"<th>שם פריט</th>"
        f"<th>מחסן</th>"
        f"<th>קיים במלאי כעת</th>"
        f"<th>סה\"כ נדרש ליעד</th>"
        f"<th>מאזן סופי (ירוק = נשאר | אדום = כמה חסר במינוס)</th>"
        f"<th>הזמנות רכש פתוחות</th>"
        f"<th>ספק ראשי (וחלופי)</th>"
        f"</tr></thead><tbody>{shortage_rows_html}</tbody></table>",
        unsafe_allow_html=True
    )

# ==============================================================================
# דף 5: העברות בין מחסנים, הזמנות רכש ו-SAP
# ==============================================================================
elif menu == UI["m_wh"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    ed_po = st.data_editor(df_po, use_container_width=True, hide_index=True, num_rows="dynamic")
    if st.button("💾 שמור הזמנות רכש"):
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
        st.success("נשמר!")
        st.rerun()

# ==============================================================================
# דף 6: סוכן פקודות מהיר
# ==============================================================================
elif menu == UI["m_ai"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_ai"]}</h2></div>', unsafe_allow_html=True)
    st.caption("כתוב פקודה כגון: `תוסיף 5 קילו ל-1001` או `תוסיף 300 יחידות ל-3001`")
    cmd_in = st.chat_input("כתוב פקודה לביצוע מיידי...")
    if cmd_in:
        nums = re.findall(r"(\d+(?:\.\d+)?)", cmd_in)
        if len(nums) >= 2:
            s_code = nums[-1]
            val = float(nums[0])
            if "קילו" in cmd_in or "kg" in cmd_in.lower():
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?", (val * 1000.0, s_code))
                conn.commit()
                st.success(f"נוספו {val} ק\"ג למק\"ט {s_code}!")
            else:
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?", (val, s_code))
                conn.commit()
                st.success(f"נוספו {val} יח' למק\"ט {s_code}!")
