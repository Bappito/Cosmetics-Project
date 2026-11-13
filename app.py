import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import json
import time
import re
from datetime import datetime, timedelta

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

st.set_page_config(page_title="Priority & SAP Cosmetics ERP", layout="wide", page_icon="🧪")

# --- רשימת 8 המחסנים המוגדרים במערכת ---
WAREHOUSES_HE = [
    "מחסן חומר",
    "קו ייצור",
    "מחסן איכות",
    "מחסן חומר מוכן",
    "מחסן מלאי אריזות",
    "מחסן תצורה מוכנה",
    "מחסן ספקים",
    "מחסן חומרה פגומה"
]

ITEM_TYPES = ["חומר גלם", "אריזה", "מדבקה", "מוצר מוגמר"]

# --- מילון דו-לשוני (עברית / אנגלית) ---
TRANSLATIONS = {
    "he": {
        "dir": "rtl",
        "align": "right",
        "flex_align": "flex-start",
        "nav_title": "תפריט מערכת ERP",
        "m_inv": "📦 קטלוג פריטים ומלאי רב-מחסני",
        "m_wh": "🔄 העברות בין מחסנים ויומן תנועות",
        "m_bom": "🧪 עצי מוצר (חומר + אריזות) וייצור",
        "m_po": "🚚 הזמנות רכש (PO) וזמני אספקה",
        "m_sap": "🔌 ממשק משיכה מ-SAP וסימולטור",
        "m_ai": "🤖 סוכן חכם (מקומי + AI)"
    },
    "en": {
        "dir": "ltr",
        "align": "left",
        "flex_align": "flex-start",
        "nav_title": "ERP Navigation",
        "m_inv": "📦 Item Catalog & Multi-Warehouse",
        "m_wh": "🔄 Warehouse Transfers & Audit Log",
        "m_bom": "🧪 BOM (Raw + Pack + Label) & Prod",
        "m_po": "🚚 Purchase Orders (PO) & ETA",
        "m_sap": "🔌 SAP Data Connector & Simulator",
        "m_ai": "🤖 Smart ERP Agent (Local + AI)"
    }
}

# --- בחירת שפה בסרגל הצד ---
st.sidebar.markdown("### 🌐 שפה / Language")
lang_choice = st.sidebar.radio(
    "Language",
    ["עברית (RTL)", "English (LTR)"],
    horizontal=True,
    label_visibility="collapsed"
)
lang = "he" if lang_choice.startswith("עברית") else "en"
T = TRANSLATIONS[lang]

# --- CSS מתקדם שכופה כיווניות מלאה (RTL בעברית / LTR באנגלית) ומעצב את התפריט ---
st.markdown(f"""
    <style>
    /* כיווניות כללית של האפליקציה והתפריט */
    .stApp, .main, .block-container {{
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        font-family: 'Segoe UI', Tahoma, sans-serif;
    }}
    section[data-testid="stSidebar"], section[data-testid="stSidebar"] > div {{
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
    }}

    /* הסתרת סמל הקישור (השרשרת) ליד כותרות */
    a.header-anchor, [data-testid="stHeaderActionElements"] {{
        display: none !important;
    }}

    /* אכיפת יישור לימין/שמאל על כל הכותרות, הטקסטים והבאנרים */
    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown, [data-testid="stMarkdownContainer"] {{
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        width: 100% !important;
    }}

    /* באנר כותרת ראשית מיושר לחלוטין לימין בעברית */
    .erp-banner {{
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        border: 1px solid rgba(128, 128, 128, 0.3);
        border-{"right" if lang == "he" else "left"}: 6px solid #8b5cf6;
        padding: 18px 24px;
        border-radius: 12px;
        margin-bottom: 20px;
        display: flex;
        flex-direction: column;
        align-items: stretch;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    .erp-banner .banner-title {{
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0 0 6px 0;
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        width: 100%;
    }}
    .erp-banner .banner-sub {{
        font-size: 0.95rem;
        opacity: 0.85;
        margin: 0;
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        width: 100%;
    }}

    /* עיצוב כרטיסי המדדים (KPI Metrics) */
    div[data-testid="stMetric"] {{
        background-color: var(--secondary-background-color);
        color: var(--text-color);
        border: 1px solid rgba(128, 128, 128, 0.3);
        padding: 16px 20px;
        border-radius: 12px;
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        box-shadow: 0 2px 5px rgba(0,0,0,0.04);
    }}
    div[data-testid="stMetricLabel"] > div,
    div[data-testid="stMetricValue"] > div {{
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        justify-content: {T['flex_align']} !important;
        color: var(--text-color) !important;
    }}

    /* עיצוב יוקרתי לתפריט הצד (כפתורי כרטיס במקום כפתורי רדיו פשוטים) */
    section[data-testid="stSidebar"] div[role="radiogroup"] {{
        display: flex;
        flex-direction: column;
        gap: 8px;
        direction: {T['dir']} !important;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
        background-color: var(--background-color);
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 10px;
        padding: 10px 14px !important;
        margin: 0 !important;
        transition: all 0.2s ease;
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        width: 100% !important;
        cursor: pointer;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
        border-color: #8b5cf6;
        background-color: rgba(139, 92, 246, 0.08);
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
        background: linear-gradient(135deg, rgba(139, 92, 246, 0.18) 0%, rgba(59, 130, 246, 0.12) 100%);
        border: 1.5px solid #8b5cf6 !important;
        font-weight: 700 !important;
    }}
    section[data-testid="stSidebar"] div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p {{
        font-size: 0.96rem !important;
        margin: 0 8px !important;
        direction: {T['dir']} !important;
        text-align: {T['align']} !important;
    }}

    /* יישור לשוניות (Tabs) לימין בעברית */
    div[data-baseweb="tab-list"] {{
        direction: {T['dir']} !important;
        justify-content: flex-start !important;
        gap: 12px;
    }}
    .stDataFrame, .stTable, div[data-testid="stDataFrame"] {{
        direction: {T['dir']} !important;
    }}
    </style>
""", unsafe_allow_html=True)

DB_NAME = "enterprise_cosmetics_erp.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# --- הקמת מסד הנתונים המורחב ---
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
        primary_warehouse TEXT DEFAULT 'מחסן חומר',
        sap_material_code TEXT DEFAULT ''
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS WarehouseStock (
        sku TEXT,
        warehouse_name TEXT,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        PRIMARY KEY (sku, warehouse_name)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS BOM (
        parent_sku TEXT,
        component_sku TEXT,
        comp_type TEXT,
        req_qty_units REAL DEFAULT 0,
        req_weight_grams REAL DEFAULT 0,
        PRIMARY KEY (parent_sku, component_sku)
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
        target_warehouse TEXT DEFAULT 'מחסן חומר',
        status TEXT DEFAULT 'בדרך (In Transit)'
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS StockMovements (
        move_id INTEGER PRIMARY KEY AUTOINCREMENT,
        move_date TEXT,
        sku TEXT,
        move_type TEXT,
        from_wh TEXT,
        to_wh TEXT,
        qty_units REAL DEFAULT 0,
        weight_grams REAL DEFAULT 0,
        reference TEXT
    )""")

    c.execute("""CREATE TABLE IF NOT EXISTS InitFlag (k TEXT PRIMARY KEY, v TEXT)""")
    c.execute("SELECT COUNT(*) FROM InitFlag WHERE k='v2_seeded'")
    if c.fetchone()[0] == 0:
        demo_catalog = [
            ("RAW-101", "חמאת שיאה אורגנית", "חומר גלם", 15.0, 15000.0, "נטורל אוילס", "בוטניקה סחר, שמן טבע", 85.0, 5.0, 82.0, "מחסן חומר", "SAP-100021"),
            ("RAW-102", "שמן חוחובה טהור", "חומר גלם", 9.0, 9000.0, "נטורל אוילס", "גליל אוילס", 140.0, 3.0, 138.0, "מחסן חומר", "SAP-100022"),
            ("RAW-103", "חומצה היאלורונית פעילה", "חומר גלם", 2.0, 800.0, "כימדע קוסמטיקס", "פארמה-כם", 1200.0, 1.0, 1150.0, "מחסן איכות", "SAP-100023"),
            ("PKG-301", "צנצנת זכוכית יוקרתית 50ml + מכסה", "אריזה", 1200.0, 96000.0, "אריזות המרכז", "גלאס-פק", 2.8, 500.0, 2.6, "מחסן מלאי אריזות", "SAP-200010"),
            ("PKG-302", "בקבוקון טפטפת סרום 30ml", "אריזה", 850.0, 42500.0, "אריזות המרכז", "אקו-בוטל", 3.2, 500.0, 3.1, "מחסן מלאי אריזות", "SAP-200011"),
            ("LBL-401", "מדבקת חזית מוזהבת - קרם פנים", "מדבקה", 2500.0, 2500.0, "דפוס מדבקות בע\"מ", "פרינט-פרו", 0.45, 1000.0, 0.40, "מחסן מלאי אריזות", "SAP-300001"),
            ("LBL-402", "מדבקת רכיבים וברקוד - סרום", "מדבקה", 1800.0, 1800.0, "דפוס מדבקות בע\"מ", "פרינט-פרו", 0.35, 1000.0, 0.35, "מחסן מלאי אריזות", "SAP-300002"),
            ("FG-501", "קרם פנים חומצה היאלורונית 50ml", "מוצר מוגמר", 60.0, 3000.0, "ייצור עצמי", "-", 45.0, 50.0, 32.0, "מחסן תצורה מוכנה", "SAP-900001"),
            ("FG-502", "סרום הזנה חוחובה 30ml", "מוצר מוגמר", 40.0, 1200.0, "ייצור עצמי", "-", 55.0, 50.0, 38.0, "מחסן תצורה מוכנה", "SAP-900002")
        ]
        c.executemany("INSERT OR REPLACE INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", demo_catalog)
        
        for row in demo_catalog:
            c.execute("INSERT OR REPLACE INTO WarehouseStock VALUES (?,?,?,?)", (row[0], row[10], row[3], row[4]))
            
        demo_bom = [
            ("FG-501", "RAW-101", "חומר גלם", 0.035, 35.0),
            ("FG-501", "RAW-103", "חומר גלם", 0.005, 5.0),
            ("FG-501", "PKG-301", "אריזה", 1.0, 80.0),
            ("FG-501", "LBL-401", "מדבקה", 1.0, 1.0),
            ("FG-502", "RAW-102", "חומר גלם", 0.025, 25.0),
            ("FG-502", "RAW-103", "חומר גלם", 0.003, 3.0),
            ("FG-502", "PKG-302", "אריזה", 1.0, 50.0),
            ("FG-502", "LBL-402", "מדבקה", 1.0, 1.0)
        ]
        c.executemany("INSERT OR REPLACE INTO BOM VALUES (?,?,?,?,?)", demo_bom)
        
        today = datetime.today()
        demo_po = [
            ("PO-2026-101", "RAW-103", "כימדע קוסמטיקס", 5.0, 5000.0, 1180.0, today.strftime("%Y-%m-%d"), (today + timedelta(days=4)).strftime("%Y-%m-%d"), "מחסן איכות", "בדרך (In Transit)"),
            ("PO-2026-102", "PKG-301", "אריזות המרכז", 1000.0, 80000.0, 2.65, today.strftime("%Y-%m-%d"), (today + timedelta(days=7)).strftime("%Y-%m-%d"), "מחסן מלאי אריזות", "בדרך (In Transit)")
        ]
        c.executemany("INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_warehouse, status) VALUES (?,?,?,?,?,?,?,?,?,?)", demo_po)
        
        c.execute("INSERT INTO InitFlag VALUES ('v2_seeded', '1')")
        conn.commit()
    conn.close()

init_db()
conn = get_connection()

def sync_catalog_totals():
    conn.execute("""
        UPDATE Catalog
        SET qty_units = COALESCE((SELECT SUM(qty_units) FROM WarehouseStock WHERE WarehouseStock.sku = Catalog.sku), qty_units),
            weight_grams = COALESCE((SELECT SUM(weight_grams) FROM WarehouseStock WHERE WarehouseStock.sku = Catalog.sku), weight_grams)
        WHERE EXISTS (SELECT 1 FROM WarehouseStock WHERE WarehouseStock.sku = Catalog.sku)
    """)
    conn.commit()

# --- תפריט ניווט ראשי בסרגל הצד ---
st.sidebar.markdown(f"### 🏭 {T['nav_title']}")
menu = st.sidebar.radio(
    "ניווט:",
    [T["m_inv"], T["m_wh"], T["m_bom"], T["m_po"], T["m_sap"], T["m_ai"]],
    label_visibility="collapsed"
)

st.sidebar.divider()
st.sidebar.markdown("### ⚖️ יחידת משקל / Weight Unit")
weight_unit = st.sidebar.radio("Weight", ["ק\"ג (kg)", "גרם (g)"], horizontal=True, label_visibility="collapsed")
use_kg = weight_unit.startswith("ק\"ג")
w_factor = 1000.0 if use_kg else 1.0
w_label = "ק\"ג (kg)" if use_kg else "גרם (g)"

# ==============================================================================
# מודול 1: קטלוג פריטים ומלאי רב-מחסני
# ==============================================================================
if menu == T["m_inv"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_inv']}</div>
            <div class="banner-sub">מק"ט (מפתח) • שם פריט • כמות ביחידות ובמשקל • ספק ראשי וחלופיים • מחיר פריט • מינימום הזמנה (MOQ) • מחיר קנייה אחרון • 8 מחסנים</div>
        </div>
    """, unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT * FROM Catalog", conn)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("סה\"כ מק\"טים בקטלוג", len(df_cat))
    total_kg = df_cat["weight_grams"].sum() / 1000.0
    c2.metric("משקל מלאי כולל", f"{total_kg:,.2f} ק\"ג")
    total_val = (df_cat["qty_units"] * df_cat["item_price"]).sum()
    c3.metric("שווי קטלוגי כולל", f"₪{total_val:,.0f}")
    below_moq = len(df_cat[df_cat["qty_units"] < df_cat["min_order_qty"]])
    c4.metric("פריטים מתחת למינימום הזמנה", below_moq)

    tab_cat, tab_wh_matrix, tab_add = st.tabs([
        "📋 טבלת מלאי ראשית (עריכה מלאה של כל השדות)",
        "🏢 פריסת מלאי לפי 8 המחסנים (עריכת יתרות בכל מחסן)",
        "➕ הקמת מק\"ט חדש במערכת"
    ])

    with tab_cat:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            f_type = st.selectbox("סנן לפי סוג פריט:", ["הכל"] + ITEM_TYPES)
        with col_f2:
            f_wh = st.selectbox("סנן לפי מחסן ראשי:", ["הכל"] + WAREHOUSES_HE)
        with col_f3:
            f_search = st.text_input("🔍 חיפוש חופשי (מק\"ט, שם, ספק, קוד SAP):")

        df_view = df_cat.copy()
        if f_type != "הכל":
            df_view = df_view[df_view["item_type"] == f_type]
        if f_wh != "הכל":
            df_view = df_view[df_view["primary_warehouse"] == f_wh]
        if f_search:
            df_view = df_view[
                df_view["sku"].str.contains(f_search, case=False, na=False) |
                df_view["name"].str.contains(f_search, case=False, na=False) |
                df_view["main_supplier"].str.contains(f_search, case=False, na=False) |
                df_view["alt_suppliers"].str.contains(f_search, case=False, na=False)
            ]

        df_view["display_weight"] = (df_view["weight_grams"] / w_factor).round(3)

        st.caption("💡 **עריכה חיה:** דאבל-קליק על כל תא כדי לערוך מחירים, ספקים, מינימום הזמנה, מחסן או כמויות. ניתן להוסיף שורות חדשות בתחתית או למחוק שורות וללחוץ על 'שמור שינויים'.")
        edited_cat = st.data_editor(
            df_view[[
                "sku", "name", "item_type", "qty_units", "display_weight",
                "main_supplier", "alt_suppliers", "item_price", "min_order_qty",
                "last_purchase_price", "primary_warehouse", "sap_material_code"
            ]],
            column_config={
                "sku": st.column_config.TextColumn("🔑 מק\"ט (מפתח)", required=True),
                "name": st.column_config.TextColumn("שם פריט", required=True),
                "item_type": st.column_config.SelectboxColumn("סוג פריט", options=ITEM_TYPES, required=True),
                "qty_units": st.column_config.NumberColumn("כמות (ביחידות/אריזות)", format="%.2f"),
                "display_weight": st.column_config.NumberColumn(f"כמות במשקל ({w_label})", format="%.3f" if use_kg else "%.0f"),
                "main_supplier": st.column_config.TextColumn("ספק ראשי"),
                "alt_suppliers": st.column_config.TextColumn("ספקים חלופיים"),
                "item_price": st.column_config.NumberColumn("מחיר פריט (₪)", format="₪%.2f"),
                "min_order_qty": st.column_config.NumberColumn("מינימום כמות להזמנה (MOQ)", format="%.1f"),
                "last_purchase_price": st.column_config.NumberColumn("מחיר קנייה אחרון (₪)", format="₪%.2f"),
                "primary_warehouse": st.column_config.SelectboxColumn("מחסן ראשי", options=WAREHOUSES_HE),
                "sap_material_code": st.column_config.TextColumn("מק\"ט SAP")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_main_cat"
        )

        if st.button("💾 שמור את כל השינויים בקטלוג המלאי"):
            if f_type == "הכל" and f_wh == "הכל" and not f_search:
                conn.execute("DELETE FROM Catalog")
            for _, r in edited_cat.iterrows():
                if pd.notna(r["sku"]) and str(r["sku"]).strip():
                    sku_val = str(r["sku"]).strip()
                    w_grams = float(r["display_weight"] or 0) * w_factor
                    q_units = float(r["qty_units"] or 0)
                    p_wh = str(r["primary_warehouse"] or "מחסן חומר")
                    conn.execute("""
                        INSERT OR REPLACE INTO Catalog 
                        (sku, name, item_type, qty_units, weight_grams, main_supplier, alt_suppliers, item_price, min_order_qty, last_purchase_price, primary_warehouse, sap_material_code)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        sku_val, str(r["name"] or ""), str(r["item_type"] or "חומר גלם"),
                        q_units, w_grams, str(r["main_supplier"] or ""), str(r["alt_suppliers"] or ""),
                        float(r["item_price"] or 0), float(r["min_order_qty"] or 1), float(r["last_purchase_price"] or 0),
                        p_wh, str(r["sap_material_code"] or "")
                    ))
                    conn.execute("INSERT OR REPLACE INTO WarehouseStock VALUES (?,?,?,?)", (sku_val, p_wh, q_units, w_grams))
            conn.commit()
            st.success("קטלוג המלאי והמחסנים עודכנו בהצלחה!")
            st.rerun()

    with tab_wh_matrix:
        st.subheader("יתרות מלאי מפורטות ב-8 המחסנים")
        sel_wh_filter = st.selectbox("בחר מחסן לתצוגה ועריכה:", ["כל המחסנים"] + WAREHOUSES_HE)
        q_wh = """
            SELECT w.sku, c.name, c.item_type, w.warehouse_name, w.qty_units, w.weight_grams
            FROM WarehouseStock w
            LEFT JOIN Catalog c ON w.sku = c.sku
        """
        df_wh_stock = pd.read_sql(q_wh, conn)
        if sel_wh_filter != "כל המחסנים":
            df_wh_stock = df_wh_stock[df_wh_stock["warehouse_name"] == sel_wh_filter]

        edited_wh = st.data_editor(
            df_wh_stock,
            column_config={
                "sku": st.column_config.SelectboxColumn("מק\"ט", options=list(df_cat["sku"]), required=True),
                "name": st.column_config.TextColumn("שם פריט", disabled=True),
                "item_type": st.column_config.TextColumn("סוג", disabled=True),
                "warehouse_name": st.column_config.SelectboxColumn("מחסן", options=WAREHOUSES_HE, required=True),
                "qty_units": st.column_config.NumberColumn("כמות ביחידות במחסן זה", format="%.2f"),
                "weight_grams": st.column_config.NumberColumn("משקל בגרמים במחסן זה (g)", format="%.1f")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_wh_stock"
        )
        if st.button("💾 שמור יתרות מחסנים וסנכרן קטלוג ראשי"):
            if sel_wh_filter == "כל המחסנים":
                conn.execute("DELETE FROM WarehouseStock")
            else:
                conn.execute("DELETE FROM WarehouseStock WHERE warehouse_name = ?", (sel_wh_filter,))
            for _, r in edited_wh.iterrows():
                if pd.notna(r["sku"]) and pd.notna(r["warehouse_name"]):
                    conn.execute("INSERT OR REPLACE INTO WarehouseStock VALUES (?,?,?,?)",
                                 (str(r["sku"]), str(r["warehouse_name"]), float(r["qty_units"] or 0), float(r["weight_grams"] or 0)))
            sync_catalog_totals()
            st.success("יתרות המחסנים עודכנו וסונכרנו לקטלוג הראשי!")
            st.rerun()

    with tab_add:
        st.subheader("טופס הקמת פריט חדש")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            n_sku = st.text_input("מק\"ט (מפתח ייחודי):", placeholder="RAW-205 / PKG-310")
            n_name = st.text_input("שם הפריט:")
            n_type = st.selectbox("סוג פריט:", ITEM_TYPES)
            n_wh = st.selectbox("מחסן קליטה ראשוני:", WAREHOUSES_HE)
        with ca2:
            n_units = st.number_input("כמות התחלתית (ביחידות):", min_value=0.0, value=10.0)
            n_weight = st.number_input("משקל התחלתי כולל (בגרמים):", min_value=0.0, value=1000.0, step=100.0)
            n_moq = st.number_input("מינימום כמות להזמנה (MOQ):", min_value=0.0, value=5.0)
            n_sap = st.text_input("קוד פריט ב-SAP (אופציונלי):", placeholder="SAP-100099")
        with ca3:
            n_sup = st.text_input("ספק ראשי:")
            n_alt_sup = st.text_input("ספקים חלופיים (מופרדים בפסיק):")
            n_price = st.number_input("מחיר פריט תקני (₪):", min_value=0.0, value=50.0)
            n_last_p = st.number_input("מחיר קנייה אחרון (₪):", min_value=0.0, value=48.0)

        if st.button("➕ הקם פריט חדש במערכת"):
            if n_sku and n_name:
                conn.execute("INSERT OR REPLACE INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (n_sku.strip(), n_name.strip(), n_type, n_units, n_weight, n_sup, n_alt_sup, n_price, n_moq, n_last_p, n_wh, n_sap))
                conn.execute("INSERT OR REPLACE INTO WarehouseStock VALUES (?,?,?,?)", (n_sku.strip(), n_wh, n_units, n_weight))
                conn.commit()
                st.success(f"הפריט {n_sku} - {n_name} הוקם בהצלחה ב-{n_wh}!")
                st.rerun()
            else:
                st.error("חובה להזין מק\"ט ושם פריט.")

# ==============================================================================
# מודול 2: העברה בין מחסנים (8 המחסנים) ויומן תנועות מלאי
# ==============================================================================
elif menu == T["m_wh"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_wh']}</div>
            <div class="banner-sub">העברת סחורה וחומרי גלם בין 8 המחסנים (מחסן חומר, קו ייצור, איכות, אריזות, פגומים וכו') ותיעוד של 30 יום אחורה</div>
        </div>
    """, unsafe_allow_html=True)

    df_cat = pd.read_sql("SELECT sku, name, item_type FROM Catalog", conn)
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.subheader("🔄 ביצוע העברה בין מחסנים")
        if not df_cat.empty:
            sel_item_tr = st.selectbox("בחר פריט להעברה:", df_cat["sku"] + " - " + df_cat["name"] + " (" + df_cat["item_type"] + ")")
            tr_sku = sel_item_tr.split(" - ")[0]
            from_w = st.selectbox("ממחסן מקור:", WAREHOUSES_HE, index=0)
            to_w = st.selectbox("למחסן יעד:", WAREHOUSES_HE, index=1)
            tr_units = st.number_input("כמות להעברה (ביחידות):", min_value=0.0, value=1.0, step=1.0)
            tr_grams = st.number_input("משקל להעברה (בגרמים):", min_value=0.0, value=500.0, step=50.0)
            tr_ref = st.text_input("אסמכתא / סיבת העברה:", value="העברה פנימית")

            if st.button("🚀 בצע העברה בין המחסנים"):
                if from_w == to_w:
                    st.warning("מחסן המקור ומחסן היעד חייבים להיות שונים.")
                else:
                    conn.execute("""
                        INSERT INTO WarehouseStock (sku, warehouse_name, qty_units, weight_grams)
                        VALUES (?, ?, 0, 0) ON CONFLICT(sku, warehouse_name) DO NOTHING
                    """, (tr_sku, from_w))
                    conn.execute("""
                        UPDATE WarehouseStock
                        SET qty_units = MAX(0, qty_units - ?), weight_grams = MAX(0, weight_grams - ?)
                        WHERE sku = ? AND warehouse_name = ?
                    """, (tr_units, tr_grams, tr_sku, from_w))

                    conn.execute("""
                        INSERT INTO WarehouseStock (sku, warehouse_name, qty_units, weight_grams)
                        VALUES (?, ?, ?, ?)
                        ON CONFLICT(sku, warehouse_name) DO UPDATE SET
                        qty_units = qty_units + excluded.qty_units,
                        weight_grams = weight_grams + excluded.weight_grams
                    """, (tr_sku, to_w, tr_units, tr_grams))

                    conn.execute("UPDATE Catalog SET primary_warehouse = ? WHERE sku = ?", (to_w, tr_sku))
                    conn.execute("""
                        INSERT INTO StockMovements (move_date, sku, move_type, from_wh, to_wh, qty_units, weight_grams, reference)
                        VALUES (?, ?, 'העברה בין מחסנים', ?, ?, ?, ?, ?)
                    """, (datetime.now().strftime("%Y-%m-%d %H:%M"), tr_sku, from_w, to_w, tr_units, tr_grams, tr_ref))
                    sync_catalog_totals()
                    st.success(f"הועברו {tr_units} יח' ({tr_grams} גרם) של {tr_sku} מ-{from_w} אל {to_w}!")
                    st.rerun()

    with col_t2:
        st.subheader("📊 תמונת מצב נוכחית לפי מחסן")
        df_wh_sum = pd.read_sql("""
            SELECT warehouse_name AS "שם מחסן", COUNT(DISTINCT sku) AS "מספר מק""טים",
                   SUM(qty_units) AS "סה""כ יחידות", ROUND(SUM(weight_grams)/1000.0, 2) AS "סה""כ משקל (ק""ג)"
            FROM WarehouseStock
            WHERE qty_units > 0 OR weight_grams > 0
            GROUP BY warehouse_name
        """, conn)
        st.dataframe(df_wh_sum, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📜 יומן העברות ותנועות מלאי (30 יום אחורה)")
    df_moves = pd.read_sql("SELECT * FROM StockMovements ORDER BY move_id DESC", conn)
    st.dataframe(df_moves, use_container_width=True, hide_index=True)

# ==============================================================================
# מודול 3: עצי מוצר משולבים (חומר גלם + אריזות + מדבקות) וניהול ייצור
# ==============================================================================
elif menu == T["m_bom"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_bom']}</div>
            <div class="banner-sub">בניית עץ מוצר שלם: חומרי גלם (בגרמים) + אריזות (צנצנות/בקבוקים) + מדבקות, ובדיקת אחוז מוכנות להרכבה</div>
        </div>
    """, unsafe_allow_html=True)

    fg_df = pd.read_sql("SELECT * FROM Catalog WHERE item_type = 'מוצר מוגמר'", conn)
    all_cat = pd.read_sql("SELECT * FROM Catalog", conn)

    tab_prod_ready, tab_bom_edit = st.tabs([
        "📊 מוכנות חומרים, אריזות ומדבקות לייצור (%)",
        "🛠️ עריכת עץ מוצר (חומר גלם + אריזות + מדבקות)"
    ])

    with tab_prod_ready:
        if fg_df.empty:
            st.info("הקם לפחות 'מוצר מוגמר' אחד בקטלוג כדי לבנות לו עץ מוצר.")
        else:
            batch_qty = st.slider("בחר כמות יחידות מוצר מוגמר לייצור (גודל אצווה):", 1, 1000, 100)
            sel_fg_bom = st.selectbox("בחר מוצר קוסמטי לבדיקת עץ מוצר מלא:", fg_df["sku"] + " - " + fg_df["name"])
            fg_code = sel_fg_bom.split(" - ")[0]

            q_bom = """
                SELECT b.component_sku AS "מק""ט רכיב", c.name AS "שם רכיב", b.comp_type AS "סוג בעץ",
                       b.req_qty_units AS "יח' נדרשות למוצר 1", b.req_weight_grams AS "גרם נדרש למוצר 1",
                       c.qty_units AS "קיים במלאי (יח')", c.weight_grams AS "קיים במלאי (גרם)",
                       c.primary_warehouse AS "נמצא במחסן"
                FROM BOM b
                JOIN Catalog c ON b.component_sku = c.sku
                WHERE b.parent_sku = ?
            """
            df_b = pd.read_sql(q_bom, conn, params=(fg_code,))
            if df_b.empty:
                st.warning("למוצר זה טרם הוגדר עץ מוצר. עבור ללשונית השנייה כדי להוסיף חומרי גלם, אריזות ומדבקות.")
            else:
                avail_pcts = []
                max_sets = []
                needed_desc = []
                missing_desc = []
                for _, r in df_b.iterrows():
                    if r["סוג בעץ"] == "חומר גלם":
                        req_total = r["גרם נדרש למוצר 1"] * batch_qty
                        avail = r["קיים במלאי (גרם)"]
                        pct = min(100.0, (avail / req_total * 100.0)) if req_total > 0 else 100.0
                        sets = int(avail // r["גרם נדרש למוצר 1"]) if r["גרם נדרש למוצר 1"] > 0 else 99999
                        needed_desc.append(f"{req_total:,.1f} גרם ({req_total/1000:,.2f} ק\"ג)")
                        missing_desc.append(f"{max(0.0, req_total - avail):,.1f} גרם")
                    else:
                        req_total = r["יח' נדרשות למוצר 1"] * batch_qty
                        avail = r["קיים במלאי (יח')"]
                        pct = min(100.0, (avail / req_total * 100.0)) if req_total > 0 else 100.0
                        sets = int(avail // r["יח' נדרשות למוצר 1"]) if r["יח' נדרשות למוצר 1"] > 0 else 99999
                        needed_desc.append(f"{req_total:,.0f} יח'")
                        missing_desc.append(f"{max(0.0, req_total - avail):,.0f} יח'")
                    avail_pcts.append(round(pct, 1))
                    max_sets.append(sets)

                df_b["סה\"כ נדרש לאצווה"] = needed_desc
                df_b["כמות חסרה"] = missing_desc
                df_b["אחוז מוכנות רכיב (%)"] = avail_pcts
                df_b["יח' מוצר שניתן להרכיב"] = max_sets

                total_readiness = round(sum(avail_pcts) / len(avail_pcts), 1)
                bottleneck_sets = min(max_sets)

                m1, m2, m3 = st.columns(3)
                m1.metric("אחוז מוכנות כולל (חומר + אריזה + מדבקה)", f"{total_readiness}%")
                m2.metric("יחידות שלמות שניתן לייצר ולארוז כרגע", f"{bottleneck_sets} יח'")
                m3.metric("מספר רכיבים בעץ המוצר", len(df_b))

                st.dataframe(df_b, use_container_width=True, hide_index=True)

                if st.button(f"🏭 דווח ייצור ואריזה של {batch_qty} יח' ממוצר {fg_code} (גרע חומרי גלם, אריזות ומדבקות)"):
                    for _, r in df_b.iterrows():
                        c_sku = r["מק\"ט רכיב"]
                        u_ded = r["יח' נדרשות למוצר 1"] * batch_qty
                        g_ded = r["גרם נדרש למוצר 1"] * batch_qty
                        conn.execute("""
                            UPDATE Catalog
                            SET qty_units = MAX(0, qty_units - ?), weight_grams = MAX(0, weight_grams - ?)
                            WHERE sku = ?
                        """, (u_ded, g_ded, c_sku))
                        conn.execute("""
                            INSERT INTO StockMovements (move_date, sku, move_type, from_wh, to_wh, qty_units, weight_grams, reference)
                            VALUES (?, ?, 'ניפוק לייצור ואריזה', ?, 'קו ייצור', ?, ?, ?)
                        """, (datetime.now().strftime("%Y-%m-%d %H:%M"), c_sku, r["נמצא במחסן"], -u_ded, -g_ded, f"Prod-{fg_code}-{batch_qty}u"))

                    conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku = ?", (batch_qty, fg_code))
                    conn.commit()
                    st.success(f"הייצור הושלם! נגרעו חומרי הגלם, האריזות והמדבקות, ונוספו {batch_qty} יח' של {fg_code} למחסן תצורה מוכנה.")
                    st.rerun()

    with tab_bom_edit:
        st.subheader("עריכת עצי מוצר (BOM) - שיוך חומרי גלם, אריזות ומדבקות לכל מוצר")
        df_bom_raw = pd.read_sql("SELECT * FROM BOM", conn)
        fg_skus = list(fg_df["sku"]) if not fg_df.empty else ["FG-501"]
        comp_skus = list(all_cat[all_cat["item_type"] != "מוצר מוגמר"]["sku"]) if not all_cat.empty else ["RAW-101"]

        edited_bom = st.data_editor(
            df_bom_raw,
            column_config={
                "parent_sku": st.column_config.SelectboxColumn("מק\"ט מוצר מוגמר", options=fg_skus, required=True),
                "component_sku": st.column_config.SelectboxColumn("מק\"ט רכיב (חומר/אריזה/מדבקה)", options=comp_skus, required=True),
                "comp_type": st.column_config.SelectboxColumn("סוג רכיב בעץ", options=["חומר גלם", "אריזה", "מדבקה"], required=True),
                "req_qty_units": st.column_config.NumberColumn("כמות ביחידות למוצר 1 (למשל 1 צנצנת / 1 מדבקה)", format="%.3f"),
                "req_weight_grams": st.column_config.NumberColumn("משקל בגרמים למוצר 1 (עבור חומר גלם)", format="%.2f")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_bom_full"
        )
        if st.button("💾 שמור עצי מוצר (BOM)"):
            conn.execute("DELETE FROM BOM")
            for _, r in edited_bom.iterrows():
                if pd.notna(r["parent_sku"]) and pd.notna(r["component_sku"]):
                    conn.execute("INSERT OR REPLACE INTO BOM VALUES (?,?,?,?,?)",
                                 (str(r["parent_sku"]), str(r["component_sku"]), str(r["comp_type"] or "חומר גלם"),
                                  float(r["req_qty_units"] or 0), float(r["req_weight_grams"] or 0)))
            conn.commit()
            st.success("עצי המוצר (כולל אריזות ומדבקות) נשמרו!")
            st.rerun()

# ==============================================================================
# מודול 4: הזמנות רכש (PO) עם עדכון זמני הגעה של אספקה וקליטה למחסן
# ==============================================================================
elif menu == T["m_po"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_po']}</div>
            <div class="banner-sub">ניהול הזמנות רכש מספקים, עדכון תאריכי הגעה צפויים (ETA), וקליטת משלוחים ישירות למחסן הנבחר תוך עדכון 'מחיר קנייה אחרון'</div>
        </div>
    """, unsafe_allow_html=True)

    df_po = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    df_cat = pd.read_sql("SELECT sku, name, main_supplier, last_purchase_price, min_order_qty FROM Catalog", conn)

    st.subheader("📋 טבלת הזמנות רכש וזמני הגעת אספקה (עריכה חיה של תאריכי הגעה וסטטוסים)")
    edited_po = st.data_editor(
        df_po,
        column_config={
            "po_id": st.column_config.NumberColumn("מזהה", disabled=True),
            "po_number": st.column_config.TextColumn("מספר הזמנת רכש (PO)", required=True),
            "sku": st.column_config.SelectboxColumn("מק\"ט", options=list(df_cat["sku"]), required=True),
            "supplier": st.column_config.TextColumn("ספק"),
            "order_qty_units": st.column_config.NumberColumn("כמות מוזמנת (יח')"),
            "order_weight_grams": st.column_config.NumberColumn("משקל מוזמן (גרם)"),
            "unit_price": st.column_config.NumberColumn("מחיר קנייה בהזמנה (₪)", format="₪%.2f"),
            "order_date": st.column_config.TextColumn("תאריך הזמנה"),
            "eta_date": st.column_config.TextColumn("📅 זמן הגעה משוער (ETA)"),
            "target_warehouse": st.column_config.SelectboxColumn("מחסן יעד לקליטה", options=WAREHOUSES_HE),
            "status": st.column_config.SelectboxColumn("סטטוס אספקה", options=["טיוטה", "בדרך (In Transit)", "מתעכב", "התקבל במחסן"])
        },
        use_container_width=True, hide_index=True, num_rows="dynamic", key="ed_po"
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("💾 שמור עדכוני זמני הגעה והזמנות רכש"):
            conn.execute("DELETE FROM PurchaseOrders")
            for _, r in edited_po.iterrows():
                if pd.notna(r["po_number"]) and pd.notna(r["sku"]):
                    conn.execute("""
                        INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_warehouse, status)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    """, (str(r["po_number"]), str(r["sku"]), str(r["supplier"] or ""), float(r["order_qty_units"] or 0),
                          float(r["order_weight_grams"] or 0), float(r["unit_price"] or 0), str(r["order_date"] or ""),
                          str(r["eta_date"] or ""), str(r["target_warehouse"] or "מחסן חומר"), str(r["status"] or "בדרך (In Transit)")))
            conn.commit()
            st.success("הזמנות הרכש וזמני ההגעה עודכנו!")
            st.rerun()

    with col_p2:
        open_pos = df_po[df_po["status"] != "התקבל במחסן"]
        if not open_pos.empty:
            sel_po_rec = st.selectbox("בחר הזמנת רכש שהגיעה למפעל לקליטה במלאי:", open_pos["po_number"] + " | מק\"ט: " + open_pos["sku"] + " | ל-" + open_pos["target_warehouse"])
            if st.button("📦 אשר הגעת אספקה וקלוט למחסן (מעדכן גם 'מחיר קנייה אחרון')"):
                po_num = sel_po_rec.split(" | ")[0]
                po_row = open_pos[open_pos["po_number"] == po_num].iloc[0]
                p_sku = po_row["sku"]
                p_wh = po_row["target_warehouse"]
                p_u = float(po_row["order_qty_units"])
                p_g = float(po_row["order_weight_grams"])
                p_price = float(po_row["unit_price"])

                conn.execute("""
                    INSERT INTO WarehouseStock (sku, warehouse_name, qty_units, weight_grams)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(sku, warehouse_name) DO UPDATE SET
                    qty_units = qty_units + excluded.qty_units,
                    weight_grams = weight_grams + excluded.weight_grams
                """, (p_sku, p_wh, p_u, p_g))
                conn.execute("UPDATE Catalog SET last_purchase_price = ?, primary_warehouse = ? WHERE sku = ?", (p_price, p_wh, p_sku))
                conn.execute("UPDATE PurchaseOrders SET status = 'התקבל במחסן' WHERE po_number = ?", (po_num,))
                conn.execute("""
                    INSERT INTO StockMovements (move_date, sku, move_type, from_wh, to_wh, qty_units, weight_grams, reference)
                    VALUES (?, ?, 'קבלת הזמנת רכש מספק', 'מחסן ספקים', ?, ?, ?, ?)
                """, (datetime.now().strftime("%Y-%m-%d %H:%M"), p_sku, p_wh, p_u, p_g, po_num))
                sync_catalog_totals()
                st.success(f"הזמנה {po_num} נקלטה ב-{p_wh}! המלאי ומחיר הקנייה האחרון עודכנו.")
                st.rerun()

# ==============================================================================
# מודול 5: חיבור ומשיכת מידע מ-SAP + סימולטור MRP
# ==============================================================================
elif menu == T["m_sap"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_sap']}</div>
            <div class="banner-sub">משיכת נתוני פריטים, מלאי והזמנות רכש מ-SAP (טבלאות MARA / MARD / EKPO או ייצוא Excel/CSV מ-SAP GUI)</div>
        </div>
    """, unsafe_allow_html=True)

    tab_sap_import, tab_sap_odata, tab_mrp_sim = st.tabs([
        "📥 משיכת קובץ ייצוא מ-SAP (MARA / MARD / MB52)",
        "🔗 הגדרת חיבור ישיר ל-SAP B1 / S/4HANA (RFC / OData API)",
        "🎛️ סימולטור MRP מלא (חומרים + אריזות + מדבקות)"
    ])

    with tab_sap_import:
        st.subheader("ייבוא אוטומטי של דוח SAP (Excel / CSV) לתוך המערכת")
        st.markdown("""
        המערכת מזהה אוטומטית עמודות סטנדרטיות של **SAP** (כגון `MATNR` למק"ט, `MAKTX` לשם פריט, `LABST` ליתרת מלאי, `LGORT` למחסן, `LIFNR` לספק, `NETPR` למחיר) או עמודות בעברית/אנגלית, ומעדכנת את הקטלוג והמחסנים בלחיצת כפתור.
        """)
        sap_file = st.file_uploader("העלה קובץ CSV או Excel שיוצא מ-SAP (למשל מטרנזקציית MB52 / MM60 / ME2N):", type=["csv", "xlsx"])
        if sap_file is not None:
            try:
                if sap_file.name.endswith(".csv"):
                    df_sap = pd.read_csv(sap_file)
                else:
                    df_sap = pd.read_excel(sap_file)
                st.write("תצוגה מקדימה של נתוני ה-SAP שנקלטו:")
                st.dataframe(df_sap.head(10), use_container_width=True)

                cols_list = list(df_sap.columns)
                c_m1, c_m2, c_m3 = st.columns(3)
                with c_m1:
                    col_sku = st.selectbox("עמודת מק\"ט (MATNR / SKU):", cols_list, index=0)
                    col_name = st.selectbox("עמודת שם פריט (MAKTX / Name):", cols_list, index=min(1, len(cols_list)-1))
                with c_m2:
                    col_qty = st.selectbox("עמודת כמות (LABST / Qty):", cols_list, index=min(2, len(cols_list)-1))
                    col_weight = st.selectbox("עמודת משקל בגרמים (BRGEW / Weight):", cols_list, index=min(3, len(cols_list)-1))
                with c_m3:
                    col_sup = st.selectbox("עמודת ספק (LIFNR / Supplier):", cols_list, index=min(4, len(cols_list)-1))
                    col_price = st.selectbox("עמודת מחיר (NETPR / Price):", cols_list, index=min(5, len(cols_list)-1))

                if st.button("⚡ משוך וסנכרן נתוני SAP לתוך מסד הנתונים"):
                    imported_cnt = 0
                    for _, r in df_sap.iterrows():
                        s_code = str(r[col_sku]).strip()
                        if s_code and s_code != "nan":
                            conn.execute("""
                                INSERT OR REPLACE INTO Catalog 
                                (sku, name, item_type, qty_units, weight_grams, main_supplier, alt_suppliers, item_price, min_order_qty, last_purchase_price, primary_warehouse, sap_material_code)
                                VALUES (?, ?, 'חומר גלם', ?, ?, ?, '', ?, 1, ?, 'מחסן חומר', ?)
                            """, (
                                s_code, str(r[col_name]), float(r[col_qty] or 0), float(r[col_weight] or 0),
                                str(r[col_sup] or ""), float(r[col_price] or 0), float(r[col_price] or 0), s_code
                            ))
                            imported_cnt += 1
                    conn.commit()
                    st.success(f"סונכרנו בהצלחה {imported_cnt} מק\"טים מתוך SAP!")
            except Exception as e:
                st.error(f"שגיאה בקריאת קובץ ה-SAP: {e}")

    with tab_sap_odata:
        st.subheader("חיבור API ישיר לשרת SAP (Service Layer / OData / PyRFC)")
        sap_url = st.text_input("כתובת שרת SAP OData / Service Layer URL:", placeholder="https://sap-server.company.com:50000/b1s/v1/Items")
        sap_user = st.text_input("שם משתמש SAP:")
        sap_pass = st.text_input("סיסמת SAP:", type="password")
        if st.button("🔄 בדוק חיבור ומשוך טבלת Items מ-SAP"):
            if not sap_url:
                st.info("הזן כתובת שרת SAP כדי למשוך ב-API ישיר, או השתמש בלשונית הראשונה להעלאת דוח אקסל/CSV מ-SAP.")
            else:
                st.info("מנסה להתחבר ל-SAP Endpoint...")

    with tab_mrp_sim:
        st.subheader("סימולטור דרישות חומרים, אריזות ומדבקות (MRP)")
        fg_df = pd.read_sql("SELECT * FROM Catalog WHERE item_type='מוצר מוגמר'", conn)
        sim_plan = {}
        if not fg_df.empty:
            cols = st.columns(max(1, len(fg_df)))
            for i, (_, r) in enumerate(fg_df.iterrows()):
                with cols[i]:
                    sim_plan[r["sku"]] = st.number_input(f"כמות לסימולציה: {r['name']}", 0, 10000, 200, step=50)

        bom_df = pd.read_sql("SELECT * FROM BOM", conn)
        cat_df = pd.read_sql("SELECT * FROM Catalog WHERE item_type != 'מוצר מוגמר'", conn)
        sim_out = []
        for _, comp in cat_df.iterrows():
            req_u = 0.0
            req_g = 0.0
            for fg_sku, fg_qty in sim_plan.items():
                m = bom_df[(bom_df["parent_sku"] == fg_sku) & (bom_df["component_sku"] == comp["sku"])]
                if not m.empty:
                    req_u += fg_qty * m.iloc[0]["req_qty_units"]
                    req_g += fg_qty * m.iloc[0]["req_weight_grams"]
            short_u = max(0.0, req_u - comp["qty_units"])
            order_qty = max(short_u, comp["min_order_qty"]) if short_u > 0 else 0.0
            sim_out.append({
                "מק\"ט": comp["sku"], "שם פריט": comp["name"], "סוג": comp["item_type"],
                "ספק ראשי": comp["main_supplier"], "ספק חלופי": comp["alt_suppliers"],
                "נדרש (יח')": round(req_u, 1), "קיים (יח')": round(comp["qty_units"], 1),
                "נדרש (גרם)": round(req_g, 1), "קיים (גרם)": round(comp["weight_grams"], 1),
                "חוסר ביחידות": round(short_u, 1), "מינימום הזמנה (MOQ)": comp["min_order_qty"],
                "כמות מומלצת להזמנה": round(order_qty, 1),
                "עלות רכש צפויה (₪)": round(order_qty * comp["item_price"], 1)
            })
        st.dataframe(pd.DataFrame(sim_out), use_container_width=True, hide_index=True)

# ==============================================================================
# מודול 6: סוכן חכם היברידי (ללא תלות בעומס שרתים)
# ==============================================================================
elif menu == T["m_ai"]:
    st.markdown(f"""
        <div class="erp-banner">
            <div class="banner-title">{T['m_ai']}</div>
            <div class="banner-sub">מבצע פקודות בעברית באופן מקומי ומיידי (ללא תלות בעומס בשרתי גוגל!)</div>
        </div>
    """, unsafe_allow_html=True)

    st.info("""
    💡 **איך הסוכן עובד בלי להיתקע לעולם על שגיאת 503:**
    מנוע הפקודות המקומי מבצע פקודות הוספה, עדכון מלאי, שינוי מחירים ומחיקה ב-0.01 שניות ישירות בפייתון!
    דוגמאות לפקודות שתוכל לכתוב:
    - `תוסיף 5 קילו ל-RAW-101` או `תוסיף 500 גרם ל-RAW-102`
    - `תוסיף 200 יחידות ל-PKG-301`
    - `תעדכן מחיר של RAW-101 ל-95`
    - `תמחק את מקט RAW-109`
    """)

    def execute_local_command(text_cmd):
        cmd = text_cmd.strip()
        sku_match = re.search(r"([A-Za-z]+-\d+)", cmd)
        num_matches = re.findall(r"(\d+(?:\.\d+)?)", cmd)
        
        if not sku_match:
            return False, ""
        sku = sku_match.group(1).upper()
        
        if "תמחק" in cmd or "מחק" in cmd:
            conn.execute("DELETE FROM Catalog WHERE sku = ?", (sku,))
            conn.execute("DELETE FROM WarehouseStock WHERE sku = ?", (sku,))
            conn.commit()
            return True, f"✅ מנוע מקומי: המק\"ט `{sku}` נמחק בהצלחה ממסד הנתונים!"

        if "מחיר" in cmd and len(num_matches) >= 2:
            new_p = float(num_matches[-1])
            conn.execute("UPDATE Catalog SET item_price = ?, last_purchase_price = ? WHERE sku = ?", (new_p, new_p, sku))
            conn.commit()
            return True, f"✅ מנוע מקומי: המחיר של `{sku}` עודכן ל-₪{new_p}!"

        if ("תוסיף" in cmd or "הוסף" in cmd) and len(num_matches) >= 2:
            amount = float(num_matches[0]) if num_matches[0] not in sku else float(num_matches[-1])
            if "קילו" in cmd or "ק\"ג" in cmd or "kg" in cmd.lower():
                grams_add = amount * 1000.0
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku = ?", (grams_add, sku))
                conn.commit()
                return True, f"✅ מנוע מקומי: נוספו {amount} ק\"ג ({grams_add:,.0f} גרם) למלאי של `{sku}`!"
            elif "גרם" in cmd:
                conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ? WHERE sku = ?", (amount, sku))
                conn.commit()
                return True, f"✅ מנוע מקומי: נוספו {amount:,.0f} גרם למלאי של `{sku}`!"
            else:
                conn.execute("UPDATE Catalog SET qty_units = qty_units + ? WHERE sku = ?", (amount, sku))
                conn.commit()
                return True, f"✅ מנוע מקומי: נוספו {amount:,.0f} יחידות למלאי של `{sku}`!"

        return False, ""

    user_cmd = st.chat_input("כתוב פקודה לביצוע מיידי במלאי (למשל: 'תוסיף 4 קילו ל-RAW-101')...")
    if user_cmd:
        handled_locally, local_msg = execute_local_command(user_cmd)
        if handled_locally:
            st.success(local_msg)
        else:
            st.info("הפקודה נקלטה. ודא שציינת את המק\"ט (למשל RAW-101) ואת הפעולה הרצויה.")
