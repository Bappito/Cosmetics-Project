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
    "he": {"RAW": "חומר גלם", "PKG": "אריזה", "LBL": "מדבקה", "FG": "מוצר מוגמר"},
    "en": {"RAW": "Raw Material", "PKG": "Packaging", "LBL": "Label", "FG": "Finished Good"}
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
        "unit_lbl": "תצוגת משקל:",
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
        "unit_lbl": "Weight Display:",
        "kg": "kg", "g": "Grams (g)"
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

# --- CSS נקי, תומך מצב כהה/בהיר, כפתור שפה צף וצביעת תאי מלאי בירוק/אדום ---
st.markdown(f"""
<style>
.stApp, .main, .block-container {{
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
    font-family: 'Segoe UI', Tahoma, sans-serif;
    padding-top: 1.2rem !important;
    padding-bottom: 4rem !important;
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
    padding: 14px 20px;
    border-radius: 10px;
    margin-bottom: 16px;
    direction: {UI['dir']} !important;
    text-align: {UI['align']} !important;
}}
div[data-testid="stMetric"] {{
    background-color: var(--secondary-background-color);
    color: var(--text-color);
    border: 1px solid rgba(128,128,128,0.22);
    padding: 12px 16px;
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
/* עיצוב טבלאות שהולכות קבוע מימין לשמאל */
.rtl-table {{
    width: 100%;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: right;
    margin: 10px 0 18px 0;
    font-size: 0.92rem;
}}
.rtl-table th, .rtl-table td {{
    border: 1px solid rgba(128,128,128,0.32);
    padding: 8px 10px;
    color: var(--text-color);
    text-align: right !important;
}}
.rtl-table th {{
    background-color: var(--secondary-background-color);
    font-weight: 700;
}}
.matrix-table {{
    width: 100%;
    border-collapse: collapse;
    direction: rtl !important;
    text-align: center;
    margin: 10px 0 20px 0;
    font-size: 0.92rem;
}}
.matrix-table th, .matrix-table td {{
    border: 1px solid rgba(128,128,128,0.35);
    padding: 8px 10px;
    color: var(--text-color);
}}
.matrix-table thead tr:first-child th {{
    background-color: rgba(124, 58, 237, 0.18);
    font-weight: 700;
    font-size: 0.98rem;
}}
.matrix-table thead tr:nth-child(2) th {{
    background-color: var(--secondary-background-color);
    font-weight: 600;
}}
.matrix-table td.parent-col {{
    text-align: right !important;
    font-weight: 700;
    background-color: var(--secondary-background-color);
    white-space: nowrap;
}}
/* עיצוב תא מק"ט אב מאוחד */
.matrix-table td.merged-parent-col {{
    text-align: center !important;
    vertical-align: middle !important;
    font-weight: 800;
    font-size: 1.05rem;
    background: linear-gradient(135deg, rgba(124, 58, 237, 0.14) 0%, rgba(124, 58, 237, 0.05) 100%);
    border-left: 3px solid #7c3aed !important;
    padding: 14px 16px !important;
    line-height: 1.4;
}}
.matrix-table tr.group-end td {{
    border-bottom: 2.5px solid rgba(124, 58, 237, 0.55) !important;
}}
/* צביעת תאי מלאי מספיק (ירוק) ומלאי חסר (אדום) - מותאם למצב בהיר וכהה */
.matrix-table td.stock-ok {{
    background-color: rgba(34, 197, 94, 0.20) !important;
    border: 1px solid rgba(34, 197, 94, 0.55) !important;
    font-weight: 700;
}}
.matrix-table td.stock-short {{
    background-color: rgba(239, 68, 68, 0.24) !important;
    border: 1px solid rgba(239, 68, 68, 0.65) !important;
    font-weight: 700;
}}
.short-sub {{
    display: block;
    font-size: 0.74rem;
    font-weight: 600;
    opacity: 0.92;
    margin-top: 2px;
}}
.legend-box {{
    display: flex;
    gap: 16px;
    align-items: center;
    margin-bottom: 8px;
    font-size: 0.9rem;
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
            ("RAW-101", "חמאת שיאה אורגנית / Shea Butter", "RAW", 15.0, 15000.0, "נטורל אוילס", "בוטניקה סחר", 85.0, 5.0, 82.0, "WH_RAW", "SAP-101"),
            ("RAW-102", "שמן חוחובה טהור / Jojoba Oil", "RAW", 9.0, 9000.0, "נטורל אוילס", "גליל אוילס", 140.0, 3.0, 138.0, "WH_RAW", "SAP-102"),
            ("RAW-103", "חומצה היאלורונית / Hyaluronic Acid", "RAW", 2.0, 800.0, "כימדע", "פארמה-כם", 1200.0, 1.0, 1150.0, "WH_QA", "SAP-103"),
            ("PKG-301", "צנצנת זכוכית 50ml / Glass Jar 50ml", "PKG", 1200.0, 96000.0, "אריזות המרכז", "גלאס-פק", 2.8, 500.0, 2.6, "WH_PACK", "SAP-301"),
            ("PKG-302", "בקבוק סרום 30ml / Serum Bottle 30ml", "PKG", 850.0, 42500.0, "אריזות המרכז", "אקו-בוטל", 3.2, 500.0, 3.1, "WH_PACK", "SAP-302"),
            ("LBL-401", "מדבקת קרם פנים / Face Cream Label", "LBL", 2500.0, 2500.0, "דפוס מדבקות", "פרינט-פרו", 0.45, 1000.0, 0.40, "WH_PACK", "SAP-401"),
            ("LBL-402", "מדבקת סרום / Serum Label", "LBL", 1800.0, 1800.0, "דפוס מדבקות", "פרינט-פרו", 0.35, 1000.0, 0.35, "WH_PACK", "SAP-402"),
            ("FG-501", "קרם פנים היאלורוני 50ml", "FG", 60.0, 3000.0, "ייצור עצמי", "-", 45.0, 50.0, 32.0, "WH_FG", "SAP-501"),
            ("FG-502", "סרום הזנה חוחובה 30ml", "FG", 40.0, 1200.0, "ייצור עצמי", "-", 55.0, 50.0, 38.0, "WH_FG", "SAP-502")
        ]
        c.executemany("INSERT INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", seed_items)
        for r in seed_items:
            c.execute("INSERT INTO WarehouseStock VALUES (?,?,?,?)", (r[0], r[10], r[3], r[4]))
            
        seed_bom = [
            ("FG-501", "RAW-101", "RAW", 0.035, 35.0),
            ("FG-501", "RAW-103", "RAW", 0.005, 5.0),
            ("FG-501", "PKG-301", "PKG", 1.0, 80.0),
            ("FG-501", "LBL-401", "LBL", 1.0, 1.0),
            ("FG-502", "RAW-102", "RAW", 0.025, 25.0),
            ("FG-502", "RAW-103", "RAW", 0.003, 3.0),
            ("FG-502", "PKG-302", "PKG", 1.0, 50.0),
            ("FG-502", "LBL-402", "LBL", 1.0, 1.0)
        ]
        c.executemany("INSERT INTO BOM VALUES (?,?,?,?,?)", seed_bom)
        
        c.execute("INSERT INTO WeeklySchedule VALUES ('FG-501', 120, 150, 100, 200, 180, 160, 220, 140)")
        c.execute("INSERT INTO WeeklySchedule VALUES ('FG-502', 80, 100, 120, 90, 110, 130, 100, 150)")
        
        today = datetime.today()
        c.execute("""
            INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, ("PO-101", "RAW-103", "כימדע", 5.0, 5000.0, 1180.0, today.strftime("%Y-%m-%d"), (today + timedelta(days=5)).strftime("%Y-%m-%d"), "WH_QA", "In Transit"))
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
w_choice = st.sidebar.radio(UI["unit_lbl"], [UI["kg"], UI["g"]], horizontal=True)
use_kg = (w_choice == UI["kg"])
w_factor = 1000.0 if use_kg else 1.0
w_label = UI["kg"] if use_kg else UI["g"]

# --- כפתור שפה צף בפינה הימנית התחתונה של המסך ---
st.button(UI["lang_btn"], on_click=toggle_language, key="floating_lang_btn")

# ==============================================================================
# 1. מסך מלאי ומחסנים - הטבלה הולכת קבוע מימין לשמאל (מק"ט בצד ימין)
# ==============================================================================
if menu == UI["m_inv"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_inv"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
    df_cat["wh_translated"] = df_cat["primary_warehouse"].apply(tr_wh)
    df_cat["type_translated"] = df_cat["item_type"].apply(tr_type)
    df_cat["disp_weight"] = (df_cat["weight_grams"] / w_factor).round(3)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("מק\"טים פעילים" if is_he else "Active SKUs", len(df_cat))
    k2.metric("משקל מלאי כולל" if is_he else "Total Weight", f"{df_cat['weight_grams'].sum()/1000:,.2f} kg")
    k3.metric("שווי מלאי" if is_he else "Inventory Value", f"₪{(df_cat['qty_units']*df_cat['item_price']).sum():,.0f}")
    k4.metric("מתחת למינימום הזמנה" if is_he else "Below MOQ", len(df_cat[df_cat["qty_units"] < df_cat["min_order_qty"]]))

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
            f"<td>{r['qty_units']:,.1f}</td>"
            f"<td>{r['disp_weight']:,.2f} {w_label}</td>"
            f"<td><b>{r['wh_translated']}</b></td>"
            f"<td>{r['main_supplier']}</td>"
            f"<td>{r['alt_suppliers']}</td>"
            f"<td>₪{r['item_price']:,.2f}</td>"
            f"<td>{r['min_order_qty']:,.0f}</td>"
            f"<td>₪{r['last_purchase_price']:,.2f}</td>"
            f"<td>{r['sap_code']}</td>"
            f"</tr>"
        )

    inv_table_html = (
        f'<table class="rtl-table">'
        f'<thead><tr>'
        f'<th>{"מק\"ט (מפתח)" if is_he else "SKU (Key)"}</th>'
        f'<th>{"שם פריט" if is_he else "Item Name"}</th>'
        f'<th>{"סוג" if is_he else "Type"}</th>'
        f'<th>{"כמות (יח\')" if is_he else "Qty (Units)"}</th>'
        f'<th>{"משקל" if is_he else "Weight"} ({w_label})</th>'
        f'<th>{"מחסן" if is_he else "Warehouse"}</th>'
        f'<th>{"ספק ראשי" if is_he else "Supplier"}</th>'
        f'<th>{"ספקים חלופיים" if is_he else "Alt Suppliers"}</th>'
        f'<th>{"מחיר פריט" if is_he else "Item Price"}</th>'
        f'<th>{"מינימום הזמנה" if is_he else "MOQ"}</th>'
        f'<th>{"מחיר קנייה אחרון" if is_he else "Last Price"}</th>'
        f'<th>{"קוד SAP" if is_he else "SAP Code"}</th>'
        f'</tr></thead>'
        f'<tbody>{inv_rows_html}</tbody>'
        f'</table>'
    )
    st.markdown(inv_table_html, unsafe_allow_html=True)

    with st.expander("✏️ עריכת מלאי, הוספת מק\"ט או מחיקה (מק\"ט מימין)" if is_he else "✏️ Edit / Add / Delete Inventory Items", expanded=False):
        rtl_cols_order = [
            "sap_code", "last_purchase_price", "min_order_qty", "item_price",
            "alt_suppliers", "main_supplier", "wh_translated", "disp_weight",
            "qty_units", "type_translated", "name", "sku"
        ]
        edited_inv = st.data_editor(
            df_v[rtl_cols_order],
            column_config={
                "sku": st.column_config.TextColumn("🔑 מק\"ט (מפתח)" if is_he else "SKU (Key)", required=True),
                "name": st.column_config.TextColumn("שם פריט" if is_he else "Item Name", required=True),
                "type_translated": st.column_config.SelectboxColumn("סוג" if is_he else "Type", options=type_options_display, required=True),
                "qty_units": st.column_config.NumberColumn("כמות (יח')" if is_he else "Qty (Units)", format="%.2f"),
                "disp_weight": st.column_config.NumberColumn(f"{'משקל' if is_he else 'Weight'} ({w_label})", format="%.3f" if use_kg else "%.0f"),
                "wh_translated": st.column_config.SelectboxColumn("מחסן" if is_he else "Warehouse", options=wh_options_display, required=True),
                "main_supplier": st.column_config.TextColumn("ספק" if is_he else "Supplier"),
                "alt_suppliers": st.column_config.TextColumn("ספקים חלופיים" if is_he else "Alt Suppliers"),
                "item_price": st.column_config.NumberColumn("מחיר פריט" if is_he else "Price", format="₪%.2f"),
                "min_order_qty": st.column_config.NumberColumn("מינימום הזמנה" if is_he else "Min Order (MOQ)", format="%.1f"),
                "last_purchase_price": st.column_config.NumberColumn("מחיר קנייה אחרון" if is_he else "Last Price", format="₪%.2f"),
                "sap_code": st.column_config.TextColumn("קוד SAP" if is_he else "SAP Code")
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
                    grams_val = float(r["disp_weight"] or 0) * w_factor
                    u_val = float(r["qty_units"] or 0)
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
# 2. עצי מוצר ותוכנית עבודה: תא מק"ט אב מאוחד + סימון ירוק/אדום לפי זמינות מלאי!
# ==============================================================================
elif menu == UI["m_bom"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_bom"]}</h2></div>', unsafe_allow_html=True)

    fg_df = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'FG'", conn)
    for _, fg_r in fg_df.iterrows():
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (fg_r["sku"],))
    conn.commit()

    sched_query = """
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
    """
    df_sched = pd.read_sql(sched_query, conn)

    st.subheader("1. תוכנית ייצור למק\"טי אב (חודשים מעל שבועות)" if is_he else "1. Master Production Schedule (Months over Weeks)")

    parent_col_title = "מק\"ט אב ושם מוצר" if is_he else "Parent SKU & Product Name"
    month1_name = PLAN_PERIODS[0][1]
    month2_name = PLAN_PERIODS[4][1]

    rows_sched_html = ""
    for _, row in df_sched.iterrows():
        rows_sched_html += (
            f"<tr>"
            f"<td class='parent-col'>{row['parent_label']}</td>"
            f"<td>{int(row['W1'])}</td><td>{int(row['W2'])}</td><td>{int(row['W3'])}</td><td>{int(row['W4'])}</td>"
            f"<td>{int(row['W5'])}</td><td>{int(row['W6'])}</td><td>{int(row['W7'])}</td><td>{int(row['W8'])}</td>"
            f"</tr>"
        )

    html_table = (
        f"<table class='matrix-table'>"
        f"<thead>"
        f"<tr><th rowspan='2' style='width:24%; text-align:right;'>{parent_col_title}</th>"
        f"<th colspan='4'>{month1_name}</th><th colspan='4'>{month2_name}</th></tr>"
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

    st.subheader("2. נגזרת עצי מוצר לפי חודשים ושבועות (חומרי גלם, אריזות ומדבקות)" if is_he else "2. BOM Component Breakdown by Months & Weeks")

    # מקרא צבעים ברור מעל הטבלה
    legend_html = (
        f"<div class='legend-box'>"
        f"<span class='legend-pill-ok'>✓ {'ירוק = יש מספיק מלאי' if is_he else 'Green = Sufficient Stock'}</span>"
        f"<span class='legend-pill-short'>⚠️ {'אדום = חוסר במלאי (מציג כמה חסר)' if is_he else 'Red = Stock Shortage'}</span>"
        f"</div>"
    )
    st.markdown(legend_html, unsafe_allow_html=True)

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

    # חישוב זמינות מלאי מצטברת לאורך השבועות (W1 -> W8) עבור כל רכיב בן
    # כך שאם חומר גלם משמש בכמה שבועות או בכמה מוצרי אב, המערכת מזהה בדיוק באיזה שבוע ייגמר המלאי!
    remaining_pool = {}
    for _, r in df_bom_sched.iterrows():
        c_sku = r["component_sku"]
        if c_sku not in remaining_pool:
            is_raw = (r["comp_type"] == "RAW")
            remaining_pool[c_sku] = float(r["avail_grams"] if is_raw else r["avail_units"])

    week_cols = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
    cell_status = {}  # (row_index, week_col) -> (is_ok, req_val, missing_val)

    for w_col in week_cols:
        for row_idx, r in df_bom_sched.iterrows():
            c_sku = r["component_sku"]
            is_raw = (r["comp_type"] == "RAW")
            per_unit_factor = float(r["req_weight_grams"] if is_raw else r["req_qty_units"])
            req_val = float(r[w_col]) * per_unit_factor
            avail_now = remaining_pool.get(c_sku, 0.0)

            if req_val <= avail_now + 1e-6:
                cell_status[(row_idx, w_col)] = (True, req_val, 0.0)
                remaining_pool[c_sku] = max(0.0, avail_now - req_val)
            else:
                missing_val = req_val - avail_now
                cell_status[(row_idx, w_col)] = (False, req_val, missing_val)
                remaining_pool[c_sku] = 0.0

    # בניית שורות הטבלה עם איחוד תאי מק"ט אב (rowspan) וצביעת כל תא בירוק או אדום
    rows_bom_html = ""
    for parent_sku, group in df_bom_sched.groupby("parent_sku", sort=False):
        span_count = len(group)
        for idx_in_group, (row_idx, r) in enumerate(group.iterrows()):
            is_raw = (r["comp_type"] == "RAW")
            per_unit_factor = r["req_weight_grams"] if is_raw else r["req_qty_units"]
            unit_suffix = "g" if is_raw else ("יח'" if is_he else "u")
            initial_stock = r["avail_grams"] if is_raw else r["avail_units"]
            is_last_in_group = (idx_in_group == span_count - 1)
            tr_class = " class='group-end'" if is_last_in_group else ""

            parent_td = ""
            if idx_in_group == 0:
                parent_td = (
                    f"<td class='merged-parent-col' rowspan='{span_count}'>"
                    f"<div style='font-size:1.1rem;'>{r['parent_sku']}</div>"
                    f"<div style='font-size:0.9rem; opacity:0.85; font-weight:600;'>{r['parent_name']}</div>"
                    f"</td>"
                )

            week_tds_html = ""
            for w_col in week_cols:
                is_ok, req_val, missing_val = cell_status[(row_idx, w_col)]
                if is_ok:
                    week_tds_html += f"<td class='stock-ok'>✓ {req_val:,.0f} {unit_suffix}</td>"
                else:
                    short_txt = f"{'חסר' if is_he else 'Short'}: {missing_val:,.0f} {unit_suffix}"
                    week_tds_html += (
                        f"<td class='stock-short'>"
                        f"⚠️ {req_val:,.0f} {unit_suffix}"
                        f"<span class='short-sub'>({short_txt})</span>"
                        f"</td>"
                    )

            rows_bom_html += (
                f"<tr{tr_class}>"
                f"{parent_td}"
                f"<td style='text-align:right;'><b>{r['component_sku']}</b> - {r['comp_name']} <span style='opacity:0.75;'>({tr_type(r['comp_type'])})</span></td>"
                f"<td><b>{per_unit_factor:g} {unit_suffix}</b></td>"
                f"<td><b>{initial_stock:,.0f} {unit_suffix}</b></td>"
                f"{week_tds_html}"
                f"</tr>"
            )

    bom_html = (
        f"<table class='matrix-table'>"
        f"<thead>"
        f"<tr>"
        f"<th rowspan='2' style='width:16%; text-align:center;'>{'מק\"ט אב' if is_he else 'Parent SKU'}</th>"
        f"<th rowspan='2' style='text-align:right;'>{'מק\"ט בן / רכיב בעץ (חומר/אריזה/מדבקה)' if is_he else 'Child Component SKU'}</th>"
        f"<th rowspan='2'>{'למוצר 1' if is_he else 'Per 1 Unit'}</th>"
        f"<th rowspan='2'>{'קיים במלאי כעת' if is_he else 'Current Stock'}</th>"
        f"<th colspan='4'>{month1_name}</th><th colspan='4'>{month2_name}</th>"
        f"</tr><tr>"
        f"<th>{PLAN_PERIODS[0][2]}</th><th>{PLAN_PERIODS[1][2]}</th><th>{PLAN_PERIODS[2][2]}</th><th>{PLAN_PERIODS[3][2]}</th>"
        f"<th>{PLAN_PERIODS[4][2]}</th><th>{PLAN_PERIODS[5][2]}</th><th>{PLAN_PERIODS[6][2]}</th><th>{PLAN_PERIODS[7][2]}</th>"
        f"</tr></thead>"
        f"<tbody>{rows_bom_html}</tbody></table>"
    )
    st.markdown(bom_html, unsafe_allow_html=True)

    with st.expander("🛠️ עריכת רכיבי עץ מוצר (חומר גלם + אריזות + מדבקות)" if is_he else "🛠️ Edit BOM Structure", expanded=False):
        df_b_raw = pd.read_sql("SELECT * FROM BOM", conn)
        ed_bom = st.data_editor(
            df_b_raw[["req_weight_grams", "req_qty_units", "comp_type", "component_sku", "parent_sku"]],
            column_config={
                "parent_sku": st.column_config.TextColumn("מק\"ט אב" if is_he else "Parent SKU", required=True),
                "component_sku": st.column_config.TextColumn("מק\"ט רכיב" if is_he else "Component SKU", required=True),
                "comp_type": st.column_config.SelectboxColumn("סוג" if is_he else "Type", options=["RAW", "PKG", "LBL"]),
                "req_qty_units": st.column_config.NumberColumn("כמות ביחידות" if is_he else "Units Needed"),
                "req_weight_grams": st.column_config.NumberColumn("משקל בגרמים" if is_he else "Grams Needed")
            },
            num_rows="dynamic", use_container_width=True, hide_index=True
        )
        if st.button("💾 שמור עץ מוצר" if is_he else "💾 Save BOM"):
            conn.execute("DELETE FROM BOM")
            for _, r in ed_bom.iterrows():
                if pd.notna(r["parent_sku"]) and pd.notna(r["component_sku"]):
                    conn.execute("INSERT OR REPLACE INTO BOM VALUES (?,?,?,?,?)",
                                 (str(r["parent_sku"]), str(r["component_sku"]), str(r["comp_type"] or "RAW"),
                                  float(r["req_qty_units"] or 0), float(r["req_weight_grams"] or 0)))
            conn.commit()
            st.rerun()

# ==============================================================================
# 3. העברות בין 8 המחסנים
# ==============================================================================
elif menu == UI["m_wh"]:
    st.markdown(f'<div class="clean-header"><h2 style="margin:0;">{UI["m_wh"]}</h2></div>', unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT sku, name, primary_warehouse FROM Catalog", conn)
    wh_display_list = list(WH_NAMES[lang].values())

    c1, c2 = st.columns(2)
    with c1:
        sel_item = st.selectbox("בחר פריט:" if is_he else "Select Item:", df_cat["sku"] + " - " + df_cat["name"])
        from_wh_disp = st.selectbox("ממחסן:" if is_he else "From Warehouse:", wh_display_list, index=0)
        to_wh_disp = st.selectbox("אל מחסן:" if is_he else "To Warehouse:", wh_display_list, index=1)
        qty_u = st.number_input("כמות (יח'):" if is_he else "Qty (Units):", min_value=0.0, value=1.0)
        qty_g = st.number_input("משקל (גרם):" if is_he else "Weight (Grams):", min_value=0.0, value=500.0)

        if st.button("🚀 בצע העברה" if is_he else "🚀 Execute Transfer"):
            sku_code = sel_item.split(" - ")[0]
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
                "order_qty_units": st.column_config.NumberColumn("כמות (יח')" if is_he else "Qty (Units)"),
                "order_weight_grams": st.column_config.NumberColumn("משקל (גרם)" if is_he else "Weight (g)"),
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

    st.caption("כתוב פקודה כגון: `תוסיף 5 קילו ל-RAW-101` או `תעדכן מחיר של RAW-102 ל-130`" if is_he else "Example: `add 5 kg to RAW-101`")
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
            else:
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku=?", (val, s_code))
                conn.commit()
                st.success(f"נוספו {val} יח' ל-{s_code}!")
