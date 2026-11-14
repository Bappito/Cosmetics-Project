import streamlit as st
import sqlite3
import pandas as pd
import re
from datetime import datetime, timedelta

st.set_page_config(page_title="Cosmetics ERP", layout="wide", page_icon="🧪")

# --- ניהול שפה ב-Session State ---
if "lang" not in st.session_state:
    st.session_state.lang = "he"

def toggle_language():
    st.session_state.lang = "en" if st.session_state.lang == "he" else "he"

lang = st.session_state.lang
is_he = (lang == "he")

# --- מיפוי דו-לשוני מלא ל-8 המחסנים ולסוגי הפריטים ---
WH_NAMES = {
    "he": {
        "WH_RAW": "מחסן חומר",
        "WH_LINE": "קו ייצור",
        "WH_QA": "מחסן איכות",
        "WH_BULK": "מחסן חומר מוכן",
        "WH_PACK": "מחסן מלאי אריזות",
        "WH_FG": "מחסן תצורה מוכנה",
        "WH_VENDOR": "מחסן ספקים",
        "WH_SCRAP": "מחסן חומרה פגומה"
    },
    "en": {
        "WH_RAW": "Raw Material WH",
        "WH_LINE": "Production Line",
        "WH_QA": "Quality Assurance WH",
        "WH_BULK": "Ready Bulk WH",
        "WH_PACK": "Packaging Stock WH",
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
    "he": {"RAW": "חומר גלם", "PKG": "אריזה (בקבוק/מכסה/מתז)", "LBL": "מדבקה", "FG": "מוצר מוגמר"},
    "en": {"RAW": "Raw Material", "PKG": "Packaging (Bottle/Cap/Pump)", "LBL": "Label", "FG": "Finished Good"}
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
        "nav_hdr": "תפריט מערכת",
        "m_inv": "📦 מלאי ומחסנים",
        "m_bom": "🗓️ עצי מוצר ותוכנית שבועות/חודשים",
        "m_wh": "🔄 העברות בין מחסנים",
        "m_po": "🚚 הזמנות רכש (PO) ו-SAP",
        "m_ai": "🤖 סוכן פקודות מהיר",
        "lang_btn": "🌐 EN | English",
        "unit_lbl": "תצוגת משקל במערכת:",
        "kg": "ק\"ג (kg)", "g": "גרם (g)"
    },
    "en": {
        "dir": "ltr", "align": "left",
        "nav_hdr": "ERP Menu",
        "m_inv": "📦 Inventory & Warehouses",
        "m_bom": "🗓️ BOM & Monthly/Weekly Plan",
        "m_wh": "🔄 Warehouse Transfers",
        "m_po": "🚚 Purchase Orders & SAP",
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

# --- CSS מותאם ל-100% מרוחב המסך ללא גלילה אופקית (גלילה למעלה-למטה בלבד) ---
st.markdown(f"""
<style>
.stApp, .main, .block-container {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    font-family: 'Segoe UI', Tahoma, sans-serif;
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    padding-left: 1.2rem !important;
    padding-right: 1.2rem !important;
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
    border-{"right" if is_he else "left"}: 5px solid #7c3aed;
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
    border: 1.5px solid #7c3aed !important;
    background-color: rgba(124, 58, 237, 0.12);
    font-weight: 600 !important;
}}
/* טבלאות שנכנסות ב-100% בדף אחד ללא גלילה לצדדים */
.rtl-table {{
    width: 100% !important;
    table-layout: auto;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: right;
    margin: 8px 0 16px 0;
    font-size: 0.88rem;
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
}}
.matrix-table {{
    width: 100% !important;
    table-layout: fixed;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: center;
    margin: 8px 0 18px 0;
    font-size: 0.86rem;
}}
.matrix-table th, .matrix-table td {{
    border: 1px solid rgba(128,128,128,0.35);
    padding: 7px 5px;
    color: var(--text-color);
    word-wrap: break-word;
    overflow-wrap: break-word;
}}
.matrix-table thead tr:first-child th {{
    background-color: rgba(124, 58, 237, 0.18);
    font-weight: 700;
    font-size: 0.94rem;
}}
.matrix-table thead tr:nth-child(2) th {{
    background-color: var(--secondary-background-color);
    font-weight: 600;
    font-size: 0.84rem;
}}
.matrix-table td.parent-col {{
    text-align: right !important;
    font-weight: 700;
    background-color: var(--secondary-background-color);
    padding: 8px 10px !important;
}}
.matrix-table td.merged-parent-col {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    font-size: 0.96rem;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.14) 0%, rgba(124, 58, 237, 0.05) 100%);
    border-left: 3px solid #7c3aed !important;
    padding: 10px 8px !important;
    line-height: 1.35;
}}
.matrix-table tr.group-end td {{
    border-bottom: 2.5px solid rgba(124, 58, 237, 0.55) !important;
}}
/* עיצוב תאי מלאי מספיק (ירוק) ומלאי חסר במינוס (אדום) מותאם לרוחב הדף */
.matrix-table td.stock-ok {{
    background-color: rgba(34, 197, 94, 0.22) !important;
    border: 1px solid rgba(34, 197, 94, 0.55) !important;
    padding: 6px 4px !important;
    vertical-align: middle;
}}
.matrix-table td.stock-short {{
    background-color: rgba(239, 68, 68, 0.26) !important;
    border: 1px solid rgba(239, 68, 68, 0.65) !important;
    padding: 6px 4px !important;
    vertical-align: middle;
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
    font-size: 1.02rem;
    font-weight: 800;
    display: inline-block;
    padding: 1px 3px;
    border-radius: 4px;
    transition: transform 0.1s ease;
}}
.cell-details:hover .cell-main-val {{
    transform: scale(1.05);
    text-decoration: underline;
}}
/* פירוט שנפתח בלחיצה מבלי לגרום לגלילה אופקית בדף */
.cell-breakdown-fit {{
    margin-top: 5px;
    padding: 5px 6px;
    border-radius: 6px;
    background-color: var(--background-color);
    border: 1px solid rgba(128,128,128,0.45);
    font-size: 0.76rem;
    font-weight: 600;
    text-align: {UI['align']};
    direction: {UI['dir']};
    line-height: 1.35;
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
/* טאב קטן צף בפינה הימנית התחתונה להחלפת שפה */
div.st-key-floating_lang_btn {{
    position: fixed !important;
    bottom: 18px !important;
    right: 22px !important;
    z-index: 999999 !important;
    width: auto !important;
}}
div.st-key-floating_lang_btn button {{
    background-color: #7c3aed !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 999px !important;
    padding: 6px 16px !important;
    font-size: 0.85rem !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.28) !important;
    cursor: pointer !important;
}}
div.st-key-floating_lang_btn button:hover {{
    background-color: #6d28d9 !important;
    transform: translateY(-1px);
}}
</style>
""", unsafe_allow_html=True)

DB_NAME = "clean_cosmetics_erp.db"

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
        main_supplier TEXT DEFAULT '',
        alt_suppliers TEXT DEFAULT '',
        item_price REAL DEFAULT 0,
        min_order_qty REAL DEFAULT 1,
        last_purchase_price REAL DEFAULT 0,
        primary_warehouse TEXT DEFAULT 'WH_RAW',
        sap_code TEXT DEFAULT ''
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS WarehouseStock (
        sku TEXT,
        wh_key TEXT,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        PRIMARY KEY (sku, wh_key)
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

    c.execute("SELECT COUNT(*) FROM Catalog")
    if c.fetchone()[0] == 0:
        seed_items = [
            ("RAW-101", "חמאת שיאה אורגנית / Shea Butter", "RAW", 0.0, 15000.0, "נטורל אוילס", "בוטניקה סחר", 85.0, 5.0, 82.0, "WH_RAW", "SAP-101"),
            ("RAW-102", "שמן חוחובה טהור / Jojoba Oil", "RAW", 0.0, 9000.0, "נטורל אוילס", "גליל אוילס", 140.0, 3.0, 138.0, "WH_RAW", "SAP-102"),
            ("RAW-103", "חומצה היאלורונית / Hyaluronic Acid", "RAW", 0.0, 800.0, "כימדע", "פארמה-כם", 1200.0, 1.0, 1150.0, "WH_QA", "SAP-103"),
            ("PKG-301", "צנצנת זכוכית 50ml + מכסה / Glass Jar", "PKG", 1200.0, 0.0, "אריזות המרכז", "גלאס-פק", 2.8, 500.0, 2.6, "WH_PACK", "SAP-301"),
            ("PKG-302", "בקבוק סרום 30ml + מתז / Serum Bottle", "PKG", 850.0, 0.0, "אריזות המרכז", "אקו-בוטל", 3.2, 500.0, 3.1, "WH_PACK", "SAP-302"),
            ("LBL-401", "מדבקת קרם פנים / Face Cream Label", "LBL", 2500.0, 0.0, "דפוס מדבקות", "פרינט-פרו", 0.45, 1000.0, 0.40, "WH_PACK", "SAP-401"),
            ("LBL-402", "מדבקת סרום / Serum Label", "LBL", 1800.0, 0.0, "דפוס מדבקות", "פרינט-פרו", 0.35, 1000.0, 0.35, "WH_PACK", "SAP-402"),
            ("FG-501", "קרם פנים היאלורוני 50ml", "FG", 60.0, 0.0, "ייצור עצמי", "-", 45.0, 50.0, 32.0, "WH_FG", "SAP-501"),
            ("FG-502", "סרום הזנה חוחובה 30ml", "FG", 40.0, 0.0, "ייצור עצמי", "-", 55.0, 50.0, 38.0, "WH_FG", "SAP-502")
        ]
        c.executemany("INSERT INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", seed_items)
        for r in seed_items:
            c.execute("INSERT INTO WarehouseStock VALUES (?,?,?,?)", (r[0], r[10], r[3], r[4]))
            
        seed_bom = [
            ("FG-501", "RAW-101", "RAW", 0.0, 35.0),
            ("FG-501", "RAW-103", "RAW", 0.0, 5.0),
            ("FG-501", "PKG-301", "PKG", 1.0, 0.0),
            ("FG-501", "LBL-401", "LBL", 1.0, 0.0),
            ("FG-502", "RAW-102", "RAW", 0.0, 25.0),
            ("FG-502", "RAW-103", "RAW", 0.0, 3.0),
            ("FG-502", "PKG-302", "PKG", 1.0, 0.0),
            ("FG-502", "LBL-402", "LBL", 1.0, 0.0)
        ]
        c.executemany("INSERT INTO BOM VALUES (?,?,?,?,?)", seed_bom)
        
        c.execute("INSERT INTO WeeklySchedule VALUES ('FG-501', 120, 150, 100, 200, 180, 160, 220, 140)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('FG-502', 80, 100, 120, 90, 110, 130, 100, 150)")
        
        today = datetime.today()
        c.execute("""
            INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("PO-101", "RAW-103", "כימדע", 0.0, 5000.0, 1180.0, today.strftime("%Y-%m-%d"), (today + timedelta(days=5)).strftime("%Y-%m-%d"), "WH_QA", "In Transit"))
        conn.commit()
    conn.close()

init_db()
conn = get_connection()

# --- סרגל צד נקי ---
st.sidebar.markdown(f"### 🧪 {UI['nav_hdr']}")
menu = st.sidebar.radio(
    "Nav",
    [UI["m_inv"], UI["m_bom"], UI["m_wh"], UI["m_po"], UI["m_ai"]],
    label_visibility="collapsed"
)

st.sidebar.divider()
w_choice = st.sidebar.radio(UI["unit_lbl"], [UI["kg"], UI["g"]], index=0, horizontal=True)
use_kg = (w_choice == UI["kg"])
w_factor = 1000.0 if use_kg else 1.0
w_label = ("ק\"ג" if is_he else "kg") if use_kg else ("גרם" if is_he else "g")
u_label = "יח'" if is_he else "u"

def fmt_val(val_in_base, is_raw_item):
    if is_raw_item:
        scaled = val_in_base / w_factor
        num_str = f"{scaled:,.2f}".rstrip("0").rstrip(".") if use_kg else f"{scaled:,.0f}"
        return f"{num_str} {w_label}"
    else:
        return f"{val_in_base:,.0f} {u_label}"

# --- כפתור שפה צף בפינה הימנית התחתונה של המסך ---
st.button(UI["lang_btn"], on_click=toggle_language, key="floating_lang_btn")

# ==============================================================================
# 1. מסך מלאי ומחסנים - מותאם ב-100% לרוחב המסך ללא גלילה לצדדים
# ==============================================================================
if menu == UI["m_inv"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_inv"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
    df_cat["wh_translated"] = df_cat["primary_warehouse"].apply(tr_wh)
    df_cat["type_translated"] = df_cat["item_type"].apply(tr_type)

    def get_stock_value(row):
        if row["item_type"] == "RAW":
            return round(float(row["weight_grams"]) / w_factor, 3)
        return round(float(row["qty_units"]), 0)

    def get_stock_formatted(row):
        return fmt_val(float(row["weight_grams"]) if row["item_type"] == "RAW" else float(row["qty_units"]), row["item_type"] == "RAW")

    def get_moq_formatted(row):
        if row["item_type"] == "RAW":
            return f"{float(row['min_order_qty']):,.1f} {'ק\"ג' if is_he else 'kg'}"
        return f"{float(row['min_order_qty']):,.0f} {u_label}"

    df_cat["stock_value_num"] = df_cat.apply(get_stock_value, axis=1)
    df_cat["stock_display_str"] = df_cat.apply(get_stock_formatted, axis=1)
    df_cat["moq_display_str"] = df_cat.apply(get_moq_formatted, axis=1)

    def calc_row_value(row):
        if row["item_type"] == "RAW":
            return (float(row["weight_grams"]) / 1000.0) * float(row["item_price"])
        return float(row["qty_units"]) * float(row["item_price"])

    total_inv_value = df_cat.apply(calc_row_value, axis=1).sum()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("מק\"טים פעילים" if is_he else "Active SKUs", len(df_cat))
    raw_sum_disp = fmt_val(df_cat[df_cat["item_type"] == "RAW"]["weight_grams"].sum(), True)
    k2.metric("משקל חומרי גלם" if is_he else "Raw Materials Weight", raw_sum_disp)
    k3.metric("יחידות אריזה ומדבקות" if is_he else "Packaging & Labels", f"{df_cat[df_cat['item_type'].isin(['PKG','LBL'])]['qty_units'].sum():,.0f} {u_label}")
    k4.metric("שווי מלאי כולל" if is_he else "Inventory Value", f"₪{total_inv_value:,.0f}")

    wh_options_display = list(WH_NAMES[lang].values())
    type_options_display = list(TYPE_NAMES[lang].values())

    f1, f2, f3 = st.columns(3)
    with f1:
        sel_wh = st.selectbox("סנן לפי מחסן:" if is_he else "Filter Warehouse:", (["הכל"] if is_he else ["All"]) + wh_options_display)
    with f2:
        sel_tp = st.selectbox("סנן לפי סוג:" if is_he else "Filter Type:", (["הכל"] if is_he else ["All"]) + type_options_display)
    with f3:
        q_txt = st.text_input("🔍 חיפוש מק\"ט / שם / ספק:" if is_he else "🔍 Search SKU / Name / Supplier:")

    df_v = df_cat.copy()
    if sel_wh not in ["הכל", "All"]:
        df_v = df_v[df_v["wh_translated"] == sel_wh]
    if sel_tp not in ["הכל", "All"]:
        df_v = df_v[df_v["type_translated"] == sel_tp]
    if q_txt:
        df_v = df_v[df_v["sku"].str.contains(q_txt, case=False, na=False) | df_v["name"].str.contains(q_txt, case=False, na=False)]

    inv_rows_html = ""
    for _, r in df_v.iterrows():
        inv_rows_html += (
            f"<tr>"
            f"<td><b>{r['sku']}</b></td>"
            f"<td>{r['name']}</td>"
            f"<td>{r['type_translated']}</td>"
            f"<td><b>{r['stock_display_str']}</b></td>"
            f"<td><b>{r['wh_translated']}</b></td>"
            f"<td>{r['main_supplier']}</td>"
            f"<td>{r['alt_suppliers']}</td>"
            f"<td>₪{r['item_price']:,.2f}</td>"
            f"<td>{r['moq_display_str']}</td>"
            f"<td>₪{r['last_purchase_price']:,.2f}</td>"
            f"<td>{r['sap_code']}</td>"
            f"</tr>"
        )

    inv_table_html = (
        f'<table class="rtl-table">'
        f'<thead><tr>'
        f'<th>{"מק\"ט" if is_he else "SKU"}</th>'
        f'<th>{"שם פריט" if is_he else "Item Name"}</th>'
        f'<th>{"סוג פריט" if is_he else "Type"}</th>'
        f'<th>{"יתרת מלאי" if is_he else "Stock"}</th>'
        f'<th>{"מחסן" if is_he else "Warehouse"}</th>'
        f'<th>{"ספק ראשי" if is_he else "Supplier"}</th>'
        f'<th>{"ספקים חלופיים" if is_he else "Alt Suppliers"}</th>'
        f'<th>{"מחיר" if is_he else "Price"}</th>'
        f'<th>{"מינימום הזמנה" if is_he else "MOQ"}</th>'
        f'<th>{"מחיר אחרון" if is_he else "Last Price"}</th>'
        f'<th>{"SAP"}</th>'
        f'</tr></thead>'
        f'<tbody>{inv_rows_html}</tbody>'
        f'</table>'
    )
    st.markdown(inv_table_html, unsafe_allow_html=True)

    with st.expander("✏️ עריכת מלאי, הוספת מק\"ט או מחיקה (מק\"ט מימין)" if is_he else "✏️ Edit / Add / Delete Inventory Items", expanded=False):
        st.caption(
            f"💡 עבור **חומר גלם** הזן את הכמות ב**{w_label}**. עבור **אריזה / מדבקה / מוצר מוגמר** הזן את הכמות ב**יחידות ({u_label})**."
            if is_he else
            f"💡 For **Raw Materials**, enter weight in **{w_label}**. For **Packaging / Labels / FG**, enter **Units**."
        )
        rtl_cols_order = [
            "sap_code", "last_purchase_price", "min_order_qty", "item_price",
            "alt_suppliers", "main_supplier", "wh_translated",
            "stock_value_num", "type_translated", "name", "sku"
        ]
        edited_inv = st.data_editor(
            df_v[rtl_cols_order],
            column_config={
                "sku": st.column_config.TextColumn("🔑 מק\"ט" if is_he else "SKU", required=True),
                "name": st.column_config.TextColumn("שם פריט" if is_he else "Item Name", required=True),
                "type_translated": st.column_config.SelectboxColumn("סוג" if is_he else "Type", options=type_options_display, required=True),
                "stock_value_num": st.column_config.NumberColumn(f"מלאי ({w_label} / יח')" if is_he else f"Stock ({w_label} / Units)", format="%.2f"),
                "wh_translated": st.column_config.SelectboxColumn("מחסן" if is_he else "Warehouse", options=wh_options_display, required=True),
                "main_supplier": st.column_config.TextColumn("ספק" if is_he else "Supplier"),
                "alt_suppliers": st.column_config.TextColumn("ספקים חלופיים" if is_he else "Alt Suppliers"),
                "item_price": st.column_config.NumberColumn("מחיר" if is_he else "Price", format="₪%.2f"),
                "min_order_qty": st.column_config.NumberColumn("מינימום הזמנה" if is_he else "MOQ", format="%.1f"),
                "last_purchase_price": st.column_config.NumberColumn("מחיר אחרון" if is_he else "Last Price", format="₪%.2f"),
                "sap_code": st.column_config.TextColumn("SAP" if is_he else "SAP Code")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="clean_inv_ed"
        )

        if st.button("💾 שמור שינויים במלאי" if is_he else "💾 Save Inventory Changes"):
            if sel_wh in ["הכל", "All"] and sel_tp in ["הכל", "All"] and not q_txt:
                conn.execute("DELETE FROM Catalog")
            for _, r in edited_inv.iterrows():
                if pd.notna(r["sku"]) and str(r["sku"]).strip():
                    s_code = str(r["sku"]).strip()
                    internal_wh = WH_TO_KEY.get(r["wh_translated"], "WH_RAW")
                    internal_type = TYPE_TO_KEY.get(r["type_translated"], "RAW")
                    val_num = float(r["stock_value_num"] or 0)
                    if internal_type == "RAW":
                        grams_val = val_num * w_factor
                        u_val = 0.0
                    else:
                        grams_val = 0.0
                        u_val = val_num

                    conn.execute("""
                        INSERT OR REPLACE INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        s_code, str(r["name"] or ""), internal_type, u_val, grams_val,
                        str(r["main_supplier"] or ""), str(r["alt_suppliers"] or ""),
                        float(r["item_price"] or 0), float(r["min_order_qty"] or 1),
                        float(r["last_purchase_price"] or 0), internal_wh, str(r["sap_code"] or "")
                    ))
            conn.commit()
            st.success("נשמר בהצלחה!" if is_he else "Saved successfully!")
            st.rerun()

# ==============================================================================
# 2. עצי מוצר ותוכנית עבודה: חיפוש לפי מק"ט אב או מק"ט בן + הכל נכנס בדף אחד בלי גלילה לצדדים!
# ==============================================================================
elif menu == UI["m_bom"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_bom"]}</h2></div>', unsafe_allow_html=True)

    fg_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'FG'", conn)
    for _, fg_r in fg_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (fg_r["sku"],))
    conn.commit()

    sched_query = """
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
    """
    df_sched = pd.read_sql(sched_query, conn)

    bom_join = """
        SELECT b.parent_sku, p.name AS parent_name,
               b.component_sku, c.name AS comp_name, b.comp_type,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        ORDER BY b.parent_sku, b.comp_type, b.component_sku
    """
    df_bom_sched = pd.read_sql(bom_join, conn)

    # --- חישוב מלאי מתגלגל על כל הנתונים (כדי שהיתרות יהיו תמיד מדויקות גם כשמסננים!) ---
    remaining_pool = {}
    for _, r in df_bom_sched.iterrows():
        c_sku = r["component_sku"]
        if c_sku not in remaining_pool:
            is_raw = (r["comp_type"] == "RAW")
            remaining_pool[c_sku] = float(r["avail_grams"] if is_raw else r["avail_units"])

    week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    cell_status = {}

    for w_col in week_cols:
        for row_idx, r in df_bom_sched.iterrows():
            c_sku = r["component_sku"]
            is_raw = (r["comp_type"] == "RAW")
            per_unit_factor = float(r["req_weight_grams"] if is_raw else r["req_qty_units"])
            used_val = float(r[w_col]) * per_unit_factor
            before_val = remaining_pool.get(c_sku, 0.0)

            if used_val <= before_val + 1e-6:
                rem_val = max(0.0, before_val - used_val)
                cell_status[(row_idx, w_col)] = {
                    "is_ok": True,
                    "before": before_val,
                    "used": used_val,
                    "rem": rem_val,
                    "missing": 0.0
                }
                remaining_pool[c_sku] = rem_val
            else:
                missing_val = used_val - before_val
                cell_status[(row_idx, w_col)] = {
                    "is_ok": False,
                    "before": before_val,
                    "used": used_val,
                    "rem": 0.0,
                    "missing": missing_val
                }
                remaining_pool[c_sku] = 0.0

    # --- סרגל חיפוש וסינון לפי מק"ט אב או מק"ט בן ---
    all_lbl = "הכל" if is_he else "All"
    parent_opts = [all_lbl] + list((df_sched["sku"] + " - " + df_sched["parent_name"]).unique())
    child_opts = [all_lbl] + list((df_bom_sched["component_sku"] + " - " + df_bom_sched["comp_name"]).unique())

    s_col1, s_col2, s_col3 = st.columns([2, 1.5, 1.5])
    with s_col1:
        bom_search_txt = st.text_input(
            "🔍 חיפוש חופשי לפי מק\"ט אב או מק\"ט בן (או שם פריט):" if is_he else "🔍 Search by Parent SKU, Child SKU, or Name:",
            placeholder="למשל: FG-501 / RAW-103 / קרם / חומצה..." if is_he else "e.g., FG-501 / RAW-103..."
        )
    with s_col2:
        sel_parent_filter = st.selectbox("סנן לפי מק\"ט אב:" if is_he else "Filter by Parent SKU:", parent_opts)
    with s_col3:
        sel_child_filter = st.selectbox("סנן לפי מק\"ט בן (רכיב):" if is_he else "Filter by Child SKU:", child_opts)

    # סינון הטבלאות לפי בחירת המשתמש
    df_bom_view = df_bom_sched.copy()
    if sel_parent_filter != all_lbl:
        p_code_sel = sel_parent_filter.split(" - ")[0]
        df_bom_view = df_bom_view[df_bom_view["parent_sku"] == p_code_sel]
    if sel_child_filter != all_lbl:
        c_code_sel = sel_child_filter.split(" - ")[0]
        df_bom_view = df_bom_view[df_bom_view["component_sku"] == c_code_sel]
    if bom_search_txt.strip():
        q = bom_search_txt.strip()
        df_bom_view = df_bom_view[
            df_bom_view["parent_sku"].str.contains(q, case=False, na=False) |
            df_bom_view["parent_name"].str.contains(q, case=False, na=False) |
            df_bom_view["component_sku"].str.contains(q, case=False, na=False) |
            df_bom_view["comp_name"].str.contains(q, case=False, na=False)
        ]

    # סינון טבלת מק"טי האב העליונה כך שתציג את מק"טי האב הרלוונטיים לחיפוש
    relevant_parents = list(df_bom_view["parent_sku"].unique())
    df_sched_view = df_sched[df_sched["sku"].isin(relevant_parents)] if (sel_parent_filter != all_lbl or sel_child_filter != all_lbl or bom_search_txt.strip()) else df_sched

    st.subheader("1. תוכנית ייצור למק\"טי אב (חודשים מעל שבועות)" if is_he else "1. Master Production Schedule (Months over Weeks)")

    parent_col_title = "מק\"ט אב ושם מוצר" if is_he else "Parent SKU & Product Name"
    month1_name = PLAN_PERIODS[0][1]
    month2_name = PLAN_PERIODS[4][1]

    rows_sched_html = ""
    for _, row in df_sched_view.iterrows():
        rows_sched_html += (
            f"<tr>"
            f"<td class='parent-col'>{row['parent_label']}</td>"
            f"<td>{int(row['W1'])} {u_label}</td><td>{int(row['W2'])} {u_label}</td><td>{int(row['W3'])} {u_label}</td><td>{int(row['W4'])} {u_label}</td>"
            f"<td>{int(row['W5'])} {u_label}</td><td>{int(row['W6'])} {u_label}</td><td>{int(row['W7'])} {u_label}</td><td>{int(row['W8'])} {u_label}</td>"
            f"</tr>"
        )

    html_table = (
        f"<table class='matrix-table'>"
        f"<thead>"
        f"<tr><th rowspan='2' style='width:20%; text-align:right;'>{parent_col_title}</th>"
        f"<th colspan='4' style='width:40%;'>{month1_name}</th><th colspan='4' style='width:40%;'>{month2_name}</th></tr>"
        f"<tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead>"
        f"<tbody>{rows_sched_html}</tbody></table>"
    )
    st.markdown(html_table, unsafe_allow_html=True)

    with st.expander("✏️ עריכת כמויות בתאים לפי שבועות" if is_he else "✏️ Edit Weekly Cell Quantities", expanded=False):
        ed_sched = st.data_editor(
            df_sched[["W8", "W7", "W6", "W5", "W4", "W3", "W2", "W1", "parent_label"]],
            column_config={
                "parent_label": st.column_config.TextColumn(parent_col_title, disabled=True),
                "W1": st.column_config.NumberColumn(f"{month1_name} | {PLAN_PERIODS[0][2]}"),
                "W2": st.column_config.NumberColumn(f"{month1_name} | {PLAN_PERIODS[1][2]}"),
                "W3": st.column_config.NumberColumn(f"{month1_name} | {PLAN_PERIODS[2][2]}"),
                "W4": st.column_config.NumberColumn(f"{month1_name} | {PLAN_PERIODS[3][2]}"),
                "W5": st.column_config.NumberColumn(f"{month2_name} | {PLAN_PERIODS[4][2]}"),
                "W6": st.column_config.NumberColumn(f"{month2_name} | {PLAN_PERIODS[5][2]}"),
                "W7": st.column_config.NumberColumn(f"{month2_name} | {PLAN_PERIODS[6][2]}"),
                "W8": st.column_config.NumberColumn(f"{month2_name} | {PLAN_PERIODS[7][2]}")
            },
            use_container_width=True, hide_index=True
        )
        if st.button("💾 שמור כמויות שבועות" if is_he else "💾 Save Weekly Plan"):
            for _, r in ed_sched.iterrows():
                p_sku = r["parent_label"].split(" - ")[0]
                conn.execute("""
                    UPDATE WeeklySchedule SET W1=?, W2=?, W3=?, W4=?, W5=?, W6=?, W7=?, W8=?
                    WHERE parent_sku=?
                """, (r["W1"], r["W2"], r["W3"], r["W4"], r["W5"], r["W6"], r["W7"], r["W8"], p_sku))
            conn.commit()
            st.rerun()

    st.divider()

    st.subheader(
        f"2. נגזרת עצי מוצר לפי חודשים ושבועות (מוצג ב-{w_label} לחומרי גלם וביח' לאריזות)"
        if is_he else
        f"2. BOM Component Breakdown (Displayed in {w_label} for Raw Materials & Units for Packaging)"
    )

    legend_html = (
        f"<div class='legend-box'>"
        f"<span class='legend-pill-ok'>{'ירוק = המלאי שיישאר אחרי השימוש באותו שבוע' if is_he else 'Green = Remaining Stock After Week Usage'}</span>"
        f"<span class='legend-pill-short'>{'אדום = במינוס הכמות שחסרה במלאי' if is_he else 'Red = Minus Missing Quantity'}</span>"
        f"<span style='opacity:0.85;'>💡 {'לחץ על כל תא כדי לראות: לפני השימוש | שימוש השבוע | נשאר במלאי' if is_he else 'Click any cell to see: Before | Used | Remaining'}</span>"
        f"</div>"
    )
    st.markdown(legend_html, unsafe_allow_html=True)

    rows_bom_html = ""
    for parent_sku, group in df_bom_view.groupby("parent_sku", sort=False):
        span_count = len(group)
        for idx_in_group, (row_idx, r) in enumerate(group.iterrows()):
            is_raw = (r["comp_type"] == "RAW")
            per_unit_base = float(r["req_weight_grams"] if is_raw else r["req_qty_units"])
            initial_stock_base = float(r["avail_grams"] if is_raw else r["avail_units"])
            is_last_in_group = (idx_in_group == span_count - 1)
            tr_class = " class='group-end'" if is_last_in_group else ""

            parent_td = ""
            if idx_in_group == 0:
                parent_td = (
                    f"<td class='merged-parent-col' rowspan='{span_count}'>"
                    f"<div>{r['parent_sku']}</div>"
                    f"<div style='font-size:0.84rem; font-weight:600; opacity:0.88;'>{r['parent_name']}</div>"
                    f"</td>"
                )

            week_tds_html = ""
            for w_col in week_cols:
                st_info = cell_status[(row_idx, w_col)]
                before_str = fmt_val(st_info["before"], is_raw)
                used_str = fmt_val(st_info["used"], is_raw)
                rem_str = fmt_val(st_info["rem"], is_raw)
                miss_str = fmt_val(st_info["missing"], is_raw)

                if is_he:
                    if st_info["is_ok"]:
                        breakdown_html = f"<div class='cell-breakdown-fit'>לפני: <b>{before_str}</b><br>שימוש: <b>{used_str}</b><br>נשאר: <b>{rem_str}</b></div>"
                    else:
                        breakdown_html = f"<div class='cell-breakdown-fit'>לפני: <b>{before_str}</b><br>דרישה: <b>{used_str}</b><br>נשאר: <b>0</b><br><span style='color:#ef4444;'>חסר: <b>{miss_str}-</b></span></div>"
                else:
                    if st_info["is_ok"]:
                        breakdown_html = f"<div class='cell-breakdown-fit'>Before: <b>{before_str}</b><br>Used: <b>{used_str}</b><br>Rem: <b>{rem_str}</b></div>"
                    else:
                        breakdown_html = f"<div class='cell-breakdown-fit'>Before: <b>{before_str}</b><br>Need: <b>{used_str}</b><br>Rem: <b>0</b><br><span style='color:#ef4444;'>Short: <b>-{miss_str}</b></span></div>"

                if st_info["is_ok"]:
                    main_label = rem_str
                    td_cls = "stock-ok"
                else:
                    scaled_miss = st_info["missing"] / (w_factor if is_raw else 1.0)
                    num_m = (f"{scaled_miss:,.2f}".rstrip("0").rstrip(".") if (is_raw and use_kg) else f"{scaled_miss:,.0f}")
                    unit_m = w_label if is_raw else u_label
                    main_label = f"<span dir='ltr'>-{num_m}</span> {unit_m}"
                    td_cls = "stock-short"

                week_tds_html += (
                    f"<td class='{td_cls}'>"
                    f"<details class='cell-details'>"
                    f"<summary><span class='cell-main-val'>{main_label}</span></summary>"
                    f"{breakdown_html}"
                    f"</details>"
                    f"</td>"
                )

            per_unit_disp = fmt_val(per_unit_base, is_raw)
            init_stock_disp = fmt_val(initial_stock_base, is_raw)

            rows_bom_html += (
                f"<tr{tr_class}>"
                f"{parent_td}"
                f"<td style='text-align:right;'><b>{r['component_sku']}</b> - {r['comp_name']}</td>"
                f"<td><b>{per_unit_disp}</b></td>"
                f"<td><b>{init_stock_disp}</b></td>"
                f"{week_tds_html}"
                f"</tr>"
            )

    bom_html = (
        f"<table class='matrix-table'>"
        f"<thead>"
        f"<tr>"
        f"<th rowspan='2' style='width:12%; text-align:center;'>{'מק\"ט אב' if is_he else 'Parent SKU'}</th>"
        f"<th rowspan='2' style='width:18%; text-align:right;'>{'מק\"ט בן / רכיב בעץ' if is_he else 'Child Component SKU'}</th>"
        f"<th rowspan='2' style='width:7%;'>{'למוצר 1' if is_he else 'Per 1'}</th>"
        f"<th rowspan='2' style='width:9%;'>{'מלאי התחלתי' if is_he else 'Init Stock'}</th>"
        f"<th colspan='4' style='width:27%;'>{month1_name}</th><th colspan='4' style='width:27%;'>{month2_name}</th>"
        f"</tr><tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead>"
        f"<tbody>{rows_bom_html}</tbody></table>"
    )
    st.markdown(bom_html, unsafe_allow_html=True)

    with st.expander("🛠️ עריכת רכיבי עץ מוצר" if is_he else "🛠️ Edit BOM Structure", expanded=False):
        df_b_raw = pd.read_sql("SELECT * FROM BOM", conn)
        df_b_raw["amount_per_unit"] = df_b_raw.apply(
            lambda r: (r["req_weight_grams"] / w_factor) if r["comp_type"] == "RAW" else r["req_qty_units"], axis=1
        )
        ed_bom = st.data_editor(
            df_b_raw[["amount_per_unit", "comp_type", "component_sku", "parent_sku"]],
            column_config={
                "parent_sku": st.column_config.TextColumn("מק\"ט אב" if is_he else "Parent SKU", required=True),
                "component_sku": st.column_config.TextColumn("מק\"ט רכיב" if is_he else "Component SKU", required=True),
                "comp_type": st.column_config.SelectboxColumn("סוג (RAW=משקל, PKG/LBL=יח')" if is_he else "Type", options=["RAW", "PKG", "LBL"], required=True),
                "amount_per_unit": st.column_config.NumberColumn(
                    f"כמות למוצר 1 ({w_label} לחו\"ג / יח' לאריזה ומדבקה)" if is_he else f"Amount per 1 unit ({w_label} or units)",
                    format="%.4f" if use_kg else "%.1f",
                    required=True
                )
            },
            num_rows="dynamic", use_container_width=True, hide_index=True
        )
        if st.button("💾 שמור עץ מוצר" if is_he else "💾 Save BOM"):
            conn.execute("DELETE FROM BOM")
            for _, r in ed_bom.iterrows():
                if pd.notna(r["parent_sku"]) and pd.notna(r["component_sku"]):
                    c_tp = str(r["comp_type"] or "RAW")
                    amt = float(r["amount_per_unit"] or 0)
                    req_g = (amt * w_factor) if c_tp == "RAW" else 0.0
                    req_u = 0.0 if c_tp == "RAW" else amt
                    conn.execute("INSERT OR REPLACE INTO BOM VALUES (?,?,?,?,?)",
                                 (str(r["parent_sku"]), str(r["component_sku"]), c_tp, req_u, req_g))
            conn.commit()
            st.rerun()

# ==============================================================================
# 3. העברות בין 8 המחסנים
# ==============================================================================
elif menu == UI["m_wh"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT sku, name, item_type, primary_warehouse FROM Catalog", conn)
    wh_display_list = list(WH_NAMES[lang].values())

    c1, c2 = st.columns(2)
    with c1:
        sel_item = st.selectbox("בחר פריט:" if is_he else "Select Item:", df_cat["sku"] + " - " + df_cat["name"])
        sku_code = sel_item.split(" - ")[0]
        sel_type = df_cat[df_cat["sku"] == sku_code]["item_type"].iloc[0]

        from_wh_disp = st.selectbox("ממחסן:" if is_he else "From Warehouse:", wh_display_list, index=0)
        to_wh_disp = st.selectbox("אל מחסן:" if is_he else "To Warehouse:", wh_display_list, index=1)

        if sel_type == "RAW":
            w_in = st.number_input(f"משקל להעברה ({w_label}):" if is_he else f"Weight to transfer ({w_label}):", min_value=0.0, value=1.0 if use_kg else 500.0)
            qty_g = w_in * w_factor
            qty_u = 0.0
        else:
            qty_u = st.number_input("כמות להעברה (ביחידות):" if is_he else "Quantity to transfer (Units):", min_value=0.0, value=50.0, step=10.0)
            qty_g = 0.0

        if st.button("🚀 בצע העברה" if is_he else "🚀 Execute Transfer"):
            f_key = WH_TO_KEY[from_wh_disp]
            t_key = WH_TO_KEY[to_wh_disp]
            conn.execute("UPDATE Catalog SET primary_warehouse = ? WHERE sku = ?", (t_key, sku_code))
            conn.execute("""
                INSERT INTO StockMovements (move_date, sku, from_wh, to_wh, qty_units, weight_grams, reference)
                VALUES (?, ?, ?, ?, ?, ?, 'Transfer')
            """, (datetime.now().strftime("%Y-%m-%d %H:%M"), sku_code, f_key, t_key, qty_u, qty_g))
            conn.commit()
            st.success("ההעברה בוצעה!" if is_he else "Transfer completed!")
            st.rerun()

    with c2:
        df_mv = pd.read_sql("SELECT * FROM StockMovements ORDER BY move_id DESC LIMIT 30", conn)
        if not df_mv.empty:
            df_mv["from_wh"] = df_mv["from_wh"].apply(tr_wh)
            df_mv["to_wh"] = df_mv["to_wh"].apply(tr_wh)
        st.dataframe(df_mv, use_container_width=True, hide_index=True)

# ==============================================================================
# 4. הזמנות רכש (PO) עם עדכון זמני הגעה + משיכה מ-SAP
# ==============================================================================
elif menu == UI["m_po"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_po"]}</h2></div>', unsafe_allow_html=True)

    t_po, t_sap = st.tabs([
        "🚚 הזמנות רכש וזמני הגעת אספקה (ETA)" if is_he else "🚚 Purchase Orders & ETA",
        "🔌 משיכת קובץ מ-SAP" if is_he else "🔌 SAP Data Import"
    ])

    with t_po:
        df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
        df_po["target_wh_disp"] = df_po["target_wh"].apply(tr_wh)
        wh_display_list = list(WH_NAMES[lang].values())

        ed_po = st.data_editor(
            df_po[["status", "target_wh_disp", "eta_date", "order_date", "unit_price", "order_weight_grams", "order_qty_units", "supplier", "sku", "po_number"]],
            column_config={
                "po_number": st.column_config.TextColumn("מס' הזמנה" if is_he else "PO #", required=True),
                "sku": st.column_config.TextColumn("מק\"ט" if is_he else "SKU", required=True),
                "supplier": st.column_config.TextColumn("ספק" if is_he else "Supplier"),
                "order_qty_units": st.column_config.NumberColumn("כמות (יח' - לאריזה/מדבקה)" if is_he else "Qty (Units)"),
                "order_weight_grams": st.column_config.NumberColumn("משקל (גרם - לחו\"ג)" if is_he else "Weight (g)"),
                "unit_price": st.column_config.NumberColumn("מחיר" if is_he else "Price", format="₪%.2f"),
                "order_date": st.column_config.TextColumn("תאריך הזמנה" if is_he else "Order Date"),
                "eta_date": st.column_config.TextColumn("📅 זמן הגעה (ETA)" if is_he else "📅 ETA Date"),
                "target_wh_disp": st.column_config.SelectboxColumn("מחסן יעד" if is_he else "Target WH", options=wh_display_list),
                "status": st.column_config.SelectboxColumn("סטטוס" if is_he else "Status", options=["In Transit", "Delayed", "Received"])
            },
            use_container_width=True, hide_index=True, num_rows="dynamic"
        )
        if st.button("💾 שמור הזמנות רכש וזמני הגעה" if is_he else "💾 Save POs & ETA"):
            conn.execute("DELETE FROM PurchaseOrders")
            for _, r in ed_po.iterrows():
                if pd.notna(r["po_number"]) and pd.notna(r["sku"]):
                    wh_k = WH_TO_KEY.get(r["target_wh_disp"], "WH_RAW")
                    conn.execute("""
                        INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (str(r["po_number"]), str(r["sku"]), str(r["supplier"] or ""), float(r["order_qty_units"] or 0),
                          float(r["order_weight_grams"] or 0), float(r["unit_price"] or 0), str(r["order_date"] or ""),
                          str(r["eta_date"] or ""), wh_k, str(r["status"] or "In Transit")))
            conn.commit()
            st.success("נשמר!" if is_he else "Saved!")
            st.rerun()

    with t_sap:
        sap_f = st.file_uploader("העלה קובץ SAP (CSV / Excel - טרנזקציות MB52 / MARA / ME2N):" if is_he else "Upload SAP Export (CSV / XLSX):", type=["csv", "xlsx"])
        if sap_f:
            df_s = pd.read_csv(sap_f) if sap_f.name.endswith(".csv") else pd.read_excel(sap_f)
            st.dataframe(df_s.head(10), use_container_width=True)

# ==============================================================================
# 5. סוכן פקודות מקומי מהיר
# ==============================================================================
elif menu == UI["m_ai"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_ai"]}</h2></div>', unsafe_allow_html=True)

    st.caption("כתוב פקודה כגון: `תוסיף 5 קילו ל-RAW-101` או `תוסיף 300 יחידות ל-PKG-301` או `תעדכן מחיר של RAW-102 ל-130`" if is_he else "Example: `add 5 kg to RAW-101`")
    cmd_in = st.chat_input("כתוב פקודה לביצוע מיידי..." if is_he else "Type command...")
    if cmd_in:
        sku_m = re.search(r"([A-Za-z]+-\d+)", cmd_in)
        nums = re.findall(r"(\d+(?:\.\d+)?)", cmd_in)
        if sku_m and len(nums) >= 2:
            s_code = sku_m.group(1).upper()
            val = float(nums[0]) if nums[0] not in s_code else float(nums[-1])
            if "מחיר" in cmd_in or "price" in cmd_in.lower():
                conn.execute("UPDATE Catalog SET item_price=?, last_purchase_price=? WHERE sku=?", (val, val, s_code))
                conn.commit()
                st.success(f"המחיר של {s_code} עודכן ל-₪{val}!")
            elif "קילו" in cmd_in or "kg" in cmd_in.lower():
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?", (val*1000.0, s_code))
                conn.commit()
                st.success(f"נוספו {val} ק\"ג ל-{s_code}!")
            elif "גרם" in cmd_in or "g" in cmd_in.lower():
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku=?", (val, s_code))
                conn.commit()
                st.success(f"נוספו {val} גרם ל-{s_code}!")
            else:
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?", (val, s_code))
                conn.commit()
                st.success(f"נוספו {val} יח' ל-{s_code}!")
