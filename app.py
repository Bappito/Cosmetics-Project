import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import json
from datetime import datetime, timedelta

try:
    from google import genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# --- הגדרות עמוד ועיצוב UI ---
st.set_page_config(page_title="Cosmetics Priority ERP & AI", layout="wide", page_icon="🧪")

st.markdown("""
    <style>
    .stApp { direction: rtl; text-align: right; font-family: 'Segoe UI', Tahoma, sans-serif; }
    div[data-testid="stSidebarNav"] { direction: rtl; }
    .stDataFrame, .stTable { direction: rtl; }
    div[data-testid="stMetric"] {
        background-color: #1e293b; border: 1px solid #334155;
        padding: 14px; border-radius: 10px;
    }
    .priority-header {
        background: linear-gradient(90deg, #0f172a 0%, #3b0764 100%);
        padding: 16px 22px; border-radius: 10px; color: white;
        margin-bottom: 18px; border-right: 6px solid #c084fc;
    }
    .kit-card {
        background-color: #1e293b; border: 1px solid #334155;
        padding: 15px; border-radius: 10px; margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

DB_NAME = "cosmetics_priority_erp.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

# --- הקמת מסד הנתונים ---
def init_db():
    conn = get_connection()
    c = conn.cursor()
    
    c.execute("""CREATE TABLE IF NOT EXISTS Items (
        item_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        warehouse_bin TEXT DEFAULT 'A-01',
        supplier TEXT DEFAULT 'ספק כללי',
        stock_grams REAL DEFAULT 0,
        safety_stock_grams REAL DEFAULT 0,
        cost_per_kg REAL DEFAULT 0
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS InventoryLog (
        trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trans_date TEXT,
        item_id TEXT,
        trans_type TEXT,
        qty_change_grams REAL,
        target_assembly TEXT,
        reference TEXT
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS BOM (
        parent_id TEXT,
        component_id TEXT,
        grams_per_unit REAL,
        PRIMARY KEY (parent_id, component_id)
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS WorkOrders (
        wo_id INTEGER PRIMARY KEY AUTOINCREMENT,
        item_id TEXT,
        qty_ordered REAL,
        start_date TEXT,
        due_date TEXT,
        status TEXT,
        priority INTEGER DEFAULT 2
    )""")
    
    c.execute("""CREATE TABLE IF NOT EXISTS AppConfig (
        cfg_key TEXT PRIMARY KEY,
        cfg_val TEXT
    )""")
    
    # טעינת נתוני דמו רק בפעם הראשונה אי-פעם
    c.execute("SELECT COUNT(*) FROM AppConfig WHERE cfg_key = 'initialized'")
    if c.fetchone()[0] == 0:
        c.execute("SELECT COUNT(*) FROM Items")
        if c.fetchone()[0] == 0:
            items_data = [
                ("RAW-101", "חמאת שיאה אורגנית", "RAW", "COOL-A01", "נטורל אוילס", 15000.0, 5000.0, 85.0),
                ("RAW-102", "שמן חוחובה טהור", "RAW", "OIL-B02", "נטורל אוילס", 8500.0, 3000.0, 140.0),
                ("RAW-103", "חומצה היאלורונית", "RAW", "ACT-S01", "כימדע קוסמטיקס", 450.0, 500.0, 1200.0),
                ("RAW-104", "ויטמין E טוקופרול", "RAW", "ACT-S02", "כימדע קוסמטיקס", 1200.0, 400.0, 320.0),
                ("RAW-105", "בסיס אמולסיה לקרם", "RAW", "BASE-C01", "בוטניקה סחר", 25000.0, 8000.0, 45.0),
                ("FG-201", "קרם פנים חומצה היאלורונית 50ml", "FG", "FG-Z1", "ייצור עצמי", 40.0, 20.0, 35.0),
                ("FG-202", "סרום הזנה ויטמין E וחוחובה 30ml", "FG", "FG-Z1", "ייצור עצמי", 15.0, 10.0, 48.0)
            ]
            c.executemany("INSERT INTO Items VALUES (?,?,?,?,?,?,?,?)", items_data)
            
            bom_data = [
                ("FG-201", "RAW-105", 35.0), ("FG-201", "RAW-101", 10.0),
                ("FG-201", "RAW-103", 3.0),  ("FG-201", "RAW-104", 2.0),
                ("FG-202", "RAW-102", 22.0), ("FG-202", "RAW-104", 5.0), ("FG-202", "RAW-103", 3.0)
            ]
            c.executemany("INSERT INTO BOM VALUES (?,?,?)", bom_data)
            
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            log_data = [
                (now_str, "RAW-101", "ניפוק לייצור", -1000.0, "FG-201 (אצווה #101)", "WO-1"),
                (now_str, "RAW-103", "ניפוק לייצור", -300.0, "FG-201 (אצווה #101)", "WO-1"),
                (now_str, "RAW-102", "קבלת סחורה מספק", 5000.0, "מלאי כללי", "PO-884")
            ]
            c.executemany("INSERT INTO InventoryLog (trans_date, item_id, trans_type, qty_change_grams, target_assembly, reference) VALUES (?,?,?,?,?,?)", log_data)
            
            today = datetime.today()
            wo_data = [
                ("FG-201", 100, today.strftime("%Y-%m-%d"), (today + timedelta(days=3)).strftime("%Y-%m-%d"), "בייצור", 1),
                ("FG-202", 80, (today + timedelta(days=1)).strftime("%Y-%m-%d"), (today + timedelta(days=5)).strftime("%Y-%m-%d"), "מתוכנן", 2)
            ]
            c.executemany("INSERT INTO WorkOrders (item_id, qty_ordered, start_date, due_date, status, priority) VALUES (?,?,?,?,?,?)", wo_data)
        c.execute("INSERT INTO AppConfig VALUES ('initialized', '1')")
        conn.commit()
    conn.close()

init_db()
conn = get_connection()

# --- חישוב אחוז זמינות חומר (בגרמים) להכנת מוצר קוסמטי ---
def calc_cosmetic_readiness(parent_id, target_units):
    query = """
        SELECT b.component_id, i.name, b.grams_per_unit, i.stock_grams, i.warehouse_bin, i.cost_per_kg
        FROM BOM b
        JOIN Items i ON b.component_id = i.item_id
        WHERE b.parent_id = ?
    """
    df = pd.read_sql(query, conn, params=(parent_id,))
    if df.empty or target_units <= 0:
        return pd.DataFrame(), 0.0, 0
    
    df["נדרש לייצור (גרם)"] = df["grams_per_unit"] * target_units
    df["נדרש לייצור (ק\"ג)"] = (df["נדרש לייצור (גרם)"] / 1000.0).round(3)
    df["קיים במלאי (גרם)"] = df["stock_grams"]
    df["קיים במלאי (ק\"ג)"] = (df["stock_grams"] / 1000.0).round(3)
    df["חסר (גרם)"] = (df["נדרש לייצור (גרם)"] - df["stock_grams"]).clip(lower=0)
    df["אחוז זמינות חומר"] = ((df["stock_grams"] / df["נדרש לייצור (גרם)"]) * 100).clip(upper=100).round(1)
    df["יח' מוצר שניתן לייצר"] = (df["stock_grams"] // df["grams_per_unit"]).astype(int)
    
    return df, round(df["אחוז זמינות חומר"].mean(), 1), int(df["יח' מוצר שניתן לייצר"].min())

# --- תפריט צד וחיבור אוטומטי ל-Gemini API ---
st.sidebar.markdown("## 🧪 Priority Cosmetics")
menu = st.sidebar.radio(
    "ניווט במערכת:",
    [
        "📦 ניהול מלאי ותנועות (Priority)",
        "⚙️ ייצור, פורמולות ומוכנות (%)",
        "🎛️ סימולטור ותוכנית עבודה",
        "🤖 סוכן AI מבצע פעולות (Gemini)",
        "🛠️ הגדרות, גיבוי וניהול נתונים"
    ]
)

st.sidebar.divider()
unit_mode = st.sidebar.radio("⚖️ יחידת תצוגת משקל במערכת:", ["קילוגרם (kg)", "גרם (g)"])
is_kg = unit_mode.startswith("קילוגרם")

st.sidebar.divider()
default_secret_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        default_secret_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

api_key = st.sidebar.text_input("🔑 Gemini API Key:", value=default_secret_key, type="password")
selected_model = st.sidebar.selectbox("מודל AI:", ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash"])

# ==============================================================================
# מודול 1: ניהול מלאי קוסמטיקה, עריכה חיה ויומן תנועות (30 יום אחורה)
# ==============================================================================
if menu == "📦 ניהול מלאי ותנועות (Priority)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">📦 ניהול מלאי חומרי גלם ומוצרים (Priority ERP)</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">עריכה מלאה מתוך האתר: הוספה, שינוי ומחיקה של חומרי גלם, מוצרים, מחירים, מיקומים ותנועות</p>
        </div>
    """, unsafe_allow_html=True)
    
    df_raw = pd.read_sql("SELECT * FROM Items WHERE category = 'RAW'", conn)
    df_fg = pd.read_sql("SELECT * FROM Items WHERE category = 'FG'", conn)
    df_raw["שווי מלאי (₪)"] = (df_raw["stock_grams"] / 1000.0) * df_raw["cost_per_kg"]
    
    k1, k2, k3 = st.columns(3)
    k1.metric("סה\"כ חומרי גלם במערכת", len(df_raw))
    k2.metric("משקל חומרי גלם כולל במחסן", f"{df_raw['stock_grams'].sum()/1000:,.2f} ק\"ג" if is_kg else f"{df_raw['stock_grams'].sum():,.0f} גרם")
    k3.metric("שווי כספי של חומרי הגלם", f"₪{df_raw['שווי מלאי (₪)'].sum():,.0f}")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🧪 עריכת מלאי חומרי גלם (RAW)",
        "🧴 עריכת מלאי מוצרים מוגמרים (FG)",
        "🔄 דיווח תנועת מלאי / ניפוק להרכבה",
        "🕒 היסטוריית תנועות (30 יום אחורה + עריכה)"
    ])
    
    with tab1:
        factor = 1000.0 if is_kg else 1.0
        unit_label = "ק\"ג" if is_kg else "גרם"
        
        st.subheader(f"טבלת חומרי גלם - עריכה, הוספה ומחיקה ישירה (מוצג ב-{unit_label})")
        st.caption("💡 **איך עורכים:** דאבל-קליק על כל תא כדי לשנות. **הוספת פריט:** לחץ על שורת ה-`+` בתחתית הטבלה. **מחיקת פריט:** סמן את הריבוע מימין לשורה, לחץ `Delete` במקלדת, ולחץ למטה על 'שמור שינויים'.")
        
        df_disp = df_raw.copy()
        df_disp["display_stock"] = (df_disp["stock_grams"] / factor).round(3)
        df_disp["display_safety"] = (df_disp["safety_stock_grams"] / factor).round(3)
        df_disp["שווי כמות נוכחית (₪)"] = ((df_disp["stock_grams"] / 1000.0) * df_disp["cost_per_kg"]).round(1)
        
        edited_raw = st.data_editor(
            df_disp[["item_id", "name", "warehouse_bin", "supplier", "display_stock", "display_safety", "cost_per_kg", "שווי כמות נוכחית (₪)"]],
            column_config={
                "item_id": st.column_config.TextColumn("מק\"ט (חובה)", required=True),
                "name": st.column_config.TextColumn("שם חומר הגלם (חובה)", required=True),
                "warehouse_bin": st.column_config.TextColumn("מיקום במחסן"),
                "supplier": st.column_config.TextColumn("ספק"),
                "display_stock": st.column_config.NumberColumn(f"מלאי נוכחי ({unit_label})", format="%.3f" if is_kg else "%.0f"),
                "display_safety": st.column_config.NumberColumn(f"מלאי ביטחון ({unit_label})", format="%.3f" if is_kg else "%.0f"),
                "cost_per_kg": st.column_config.NumberColumn("מחיר ל-1 ק\"ג (₪)", format="₪%.2f"),
                "שווי כמות נוכחית (₪)": st.column_config.NumberColumn("שווי המלאי (₪)", disabled=True, format="₪%.1f")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_raw"
        )
        
        if st.button("💾 שמור שינויים בחומרי הגלם (כולל הוספות ומחיקות)"):
            conn.execute("DELETE FROM Items WHERE category = 'RAW'")
            for _, r in edited_raw.iterrows():
                if pd.notna(r["item_id"]) and str(r["item_id"]).strip() != "":
                    s_grams = float(r["display_stock"] or 0) * factor
                    safe_grams = float(r["display_safety"] or 0) * factor
                    conn.execute("""
                        INSERT INTO Items (item_id, name, category, warehouse_bin, supplier, stock_grams, safety_stock_grams, cost_per_kg)
                        VALUES (?, ?, 'RAW', ?, ?, ?, ?, ?)
                    """, (str(r["item_id"]).strip(), str(r["name"] or "חומר חדש").strip(), str(r["warehouse_bin"] or "A-01"), str(r["supplier"] or "כללי"), s_grams, safe_grams, float(r["cost_per_kg"] or 0)))
            conn.commit()
            st.success("טבלת חומרי הגלם עודכנה במלואה!")
            st.rerun()

    with tab2:
        st.subheader("טבלת מוצרים קוסמטיים מוגמרים (FG) - עריכה, הוספה ומחיקה")
        edited_fg = st.data_editor(
            df_fg[["item_id", "name", "warehouse_bin", "stock_grams", "safety_stock_grams", "cost_per_kg"]],
            column_config={
                "item_id": st.column_config.TextColumn("מק\"ט מוצר (למשל FG-205)", required=True),
                "name": st.column_config.TextColumn("שם המוצר הקוסמטי", required=True),
                "warehouse_bin": st.column_config.TextColumn("מיקום במחסן"),
                "stock_grams": st.column_config.NumberColumn("יתרה במלאי (יחידות)", format="%.0f"),
                "safety_stock_grams": st.column_config.NumberColumn("מלאי ביטחון (יחידות)", format="%.0f"),
                "cost_per_kg": st.column_config.NumberColumn("עלות/מחיר ליחידה (₪)", format="₪%.2f")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_fg"
        )
        if st.button("💾 שמור שינויים במוצרים המוגמרים"):
            conn.execute("DELETE FROM Items WHERE category = 'FG'")
            for _, r in edited_fg.iterrows():
                if pd.notna(r["item_id"]) and str(r["item_id"]).strip() != "":
                    conn.execute("""
                        INSERT INTO Items (item_id, name, category, warehouse_bin, supplier, stock_grams, safety_stock_grams, cost_per_kg)
                        VALUES (?, ?, 'FG', ?, 'ייצור עצמי', ?, ?, ?)
                    """, (str(r["item_id"]).strip(), str(r["name"] or "מוצר חדש").strip(), str(r["warehouse_bin"] or "FG-Z1"), float(r["stock_grams"] or 0), float(r["safety_stock_grams"] or 0), float(r["cost_per_kg"] or 0)))
            conn.commit()
            st.success("טבלת המוצרים המוגמרים עודכנה!")
            st.rerun()

    with tab3:
        st.subheader("עדכון תנועת מלאי (קליטת סחורה / ניפוק להרכבה)")
        if df_raw.empty:
            st.warning("אין חומרי גלם במערכת. הוסף חומרי גלם בלשונית הראשונה.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                sel_raw = st.selectbox("בחר חומר גלם:", df_raw["item_id"] + " - " + df_raw["name"])
                t_type = st.selectbox("סוג פעולה:", ["📤 ניפוק להרכבה / ייצור (-)", "📥 קבלת חומר גלם מספק (+)", "⚖️ ספירת מלאי (קביעת יתרה חדשה)"])
                t_unit = st.radio("הזן כמות ב:", ["גרם (g)", "קילוגרם (kg)"], horizontal=True)
                t_val = st.number_input("כמות לתנועה:", min_value=0.0, value=250.0, step=10.0)
            with c2:
                assm_options = ["מלאי כללי / מחסן"] + (list(df_fg["item_id"] + " - " + df_fg["name"]) if not df_fg.empty else [])
                target_assm = st.selectbox("שיוך להרכבה / מוצר (לאן הלך החומר):", assm_options)
                ref_txt = st.text_input("מספר אצווה (Batch) / תעודת משלוח / הערה:", value="Batch-105")
                
                if st.button("בצע עדכון מלאי ורשום ביומן"):
                    code = sel_raw.split(" - ")[0]
                    grams_delta_abs = t_val * 1000.0 if t_unit.startswith("קילוגרם") else t_val
                    curr_g = df_raw[df_raw["item_id"] == code]["stock_grams"].iloc[0]
                    
                    if "ניפוק" in t_type:
                        new_g = max(0.0, curr_g - grams_delta_abs)
                        signed_delta = -grams_delta_abs
                    elif "קבלת" in t_type:
                        new_g = curr_g + grams_delta_abs
                        signed_delta = grams_delta_abs
                    else:
                        new_g = grams_delta_abs
                        signed_delta = grams_delta_abs - curr_g
                        
                    conn.execute("UPDATE Items SET stock_grams = ? WHERE item_id = ?", (new_g, code))
                    conn.execute("""
                        INSERT INTO InventoryLog (trans_date, item_id, trans_type, qty_change_grams, target_assembly, reference)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (datetime.now().strftime("%Y-%m-%d %H:%M"), code, t_type, signed_delta, target_assm, ref_txt))
                    conn.commit()
                    st.success(f"המלאי עודכן! יתרה חדשה: {new_g:,.0f} גרם ({new_g/1000:,.2f} ק\"ג)")
                    st.rerun()

    with tab4:
        st.subheader("מעקב תנועות מלאי (30 יום אחורה) - לאיזו הרכבה הלך כל חומר")
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query_log = """
            SELECT l.trans_id, l.trans_date, l.item_id,
                   COALESCE(i.name, l.item_id) AS item_name, l.trans_type,
                   l.qty_change_grams,
                   ROUND(l.qty_change_grams / 1000.0, 3) AS qty_kg,
                   l.target_assembly, l.reference
            FROM InventoryLog l
            LEFT JOIN Items i ON l.item_id = i.item_id
            WHERE l.trans_date >= ?
            ORDER BY l.trans_id DESC
        """
        df_log = pd.read_sql(query_log, conn, params=(cutoff_date,))
        filter_opts = ["הצג את כל התנועות"] + (list(df_raw["item_id"] + " - " + df_raw["name"]) if not df_raw.empty else [])
        filter_item_log = st.selectbox("סנן היסטוריה לפי חומר גלם:", filter_opts)
        if filter_item_log != "הצג את כל התנועות":
            f_code = filter_item_log.split(" - ")[0]
            df_log = df_log[df_log["item_id"] == f_code]
            
        edited_log = st.data_editor(
            df_log,
            column_config={
                "trans_id": st.column_config.NumberColumn("מס'", disabled=True),
                "trans_date": st.column_config.TextColumn("תאריך ושעה"),
                "item_id": st.column_config.TextColumn("מק\"ט"),
                "item_name": st.column_config.TextColumn("שם חומר גלם", disabled=True),
                "trans_type": st.column_config.TextColumn("סוג תנועה"),
                "qty_change_grams": st.column_config.NumberColumn("שינוי בגרמים (g)"),
                "qty_kg": st.column_config.NumberColumn("שינוי בק\"ג (kg)", disabled=True),
                "target_assembly": st.column_config.TextColumn("שויך להרכבה / מוצר"),
                "reference": st.column_config.TextColumn("אצווה / אסמכתא")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_log"
        )
        if st.button("💾 שמור שינויים/מחיקות ביומן התנועות"):
            keep_ids = [int(r["trans_id"]) for _, r in edited_log.iterrows() if pd.notna(r["trans_id"])]
            if keep_ids:
                placeholders = ",".join(["?"] * len(keep_ids))
                conn.execute(f"DELETE FROM InventoryLog WHERE trans_date >= ? AND trans_id NOT IN ({placeholders})", [cutoff_date] + keep_ids)
            else:
                conn.execute("DELETE FROM InventoryLog WHERE trans_date >= ?", (cutoff_date,))
            for _, r in edited_log.iterrows():
                if pd.notna(r["trans_id"]):
                    conn.execute("""
                        UPDATE InventoryLog SET trans_date=?, item_id=?, trans_type=?, qty_change_grams=?, target_assembly=?, reference=?
                        WHERE trans_id=?
                    """, (r["trans_date"], r["item_id"], r["trans_type"], float(r["qty_change_grams"] or 0), r["target_assembly"], r["reference"], int(r["trans_id"])))
            conn.commit()
            st.success("יומן התנועות עודכן!")
            st.rerun()

# ==============================================================================
# מודול 2: ניהול ייצור, עריכת עצי מוצר בטבלה חיה ואחוז מוכנות חומר
# ==============================================================================
elif menu == "⚙️ ייצור, פורמולות ומוכנות (%)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">⚙️ ניהול ייצור, עצי מוצר (בגרמים) ואחוז חומר מהמלאי</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">בניית ועריכת פורמולות קוסמטיות בגרמים ישירות בטבלה, בדיקת אחוז החומר במלאי ודיווח אצוות</p>
        </div>
    """, unsafe_allow_html=True)

    fg_df = pd.read_sql("SELECT * FROM Items WHERE category='FG'", conn)
    raw_df = pd.read_sql("SELECT * FROM Items WHERE category='RAW'", conn)

    tab_readiness, tab_bom_editor = st.tabs([
        "📊 אחוז מוכנות חומרים מהמלאי וייצור אצוות",
        "🧪 עריכת עצי מוצר / פורמולות בטבלה חיה (בגרמים)"
    ])

    with tab_readiness:
        if fg_df.empty:
            st.info("אין מוצרים מוגמרים (FG). הוסף מוצר בלשונית 'עריכת מלאי מוצרים מוגמרים'.")
        else:
            batch_size = st.slider("בחר כמות יחידות מוצר (גודל אצווה) לבדיקת אחוז חומר קיים במלאי:", 1, 500, 100)
            cols = st.columns(max(1, len(fg_df)))
            for idx, (_, fg) in enumerate(fg_df.iterrows()):
                _, pct, max_u = calc_cosmetic_readiness(fg["item_id"], batch_size)
                color = "#22c55e" if pct == 100 else ("#f59e0b" if pct >= 70 else "#ef4444")
                with cols[idx]:
                    st.markdown(f"""
                        <div class="kit-card" style="border-top: 5px solid {color};">
                            <h4 style="margin:0;">{fg['name']} ({fg['item_id']})</h4>
                            <h2 style="margin:8px 0; color:{color};">{pct}% חומר זמין במלאי</h2>
                            <p style="margin:0;">🧴 עבור אצווה של {batch_size} יח' | ניתן לייצר כרגע: <b>{max_u} יח' שלמות</b></p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.progress(int(pct))

            st.divider()
            sel_fg = st.selectbox("בחר מוצר קוסמטי לפירוט מדויק של חומרי הגלם והאחוזים:", fg_df["item_id"] + " - " + fg_df["name"])
            sel_fg_code = sel_fg.split(" - ")[0]
            df_kit, _, _ = calc_cosmetic_readiness(sel_fg_code, batch_size)
            if df_kit.empty:
                st.warning("למוצר זה עדיין לא הוגדרו רכיבים בעץ המוצר (BOM). עבור ללשונית השניה כדי להגדיר פורמולה.")
            else:
                st.dataframe(df_kit, use_container_width=True, hide_index=True)
                if st.button(f"✅ בצע ייצור של {batch_size} יח' ממוצר {sel_fg_code} (גרע גרמים מהמלאי ורשום ביומן)"):
                    for _, comp in df_kit.iterrows():
                        req_g = comp["נדרש לייצור (גרם)"]
                        conn.execute("UPDATE Items SET stock_grams = MAX(0, stock_grams - ?) WHERE item_id = ?", (req_g, comp["component_id"]))
                        conn.execute("""
                            INSERT INTO InventoryLog (trans_date, item_id, trans_type, qty_change_grams, target_assembly, reference)
                            VALUES (?, ?, 'ניפוק אוטומטי לייצור', ?, ?, ?)
                        """, (datetime.now().strftime("%Y-%m-%d %H:%M"), comp["component_id"], -req_g, sel_fg, f"Batch-{batch_size}u"))
                    conn.execute("UPDATE Items SET stock_grams = stock_grams + ? WHERE item_id = ?", (batch_size, sel_fg_code))
                    conn.commit()
                    st.success(f"הייצור בוצע! חומרי הגלם נגרעו בגרמים ונרשמו ביומן התנועות תחת '{sel_fg}'.")
                    st.rerun()

    with tab_bom_editor:
        st.subheader("טבלת עצי מוצר (BOM) - עריכה, הוספה ומחיקה של פורמולות בגרמים")
        st.caption("💡 הוסף שורות חדשות, שנה את כמות הגרמים ליחידת מוצר או מחק רכיבים מהפורמולה ולחץ על שמירה.")
        
        df_bom_all = pd.read_sql("SELECT parent_id, component_id, grams_per_unit FROM BOM", conn)
        fg_ids = list(fg_df["item_id"]) if not fg_df.empty else ["FG-201"]
        raw_ids = list(raw_df["item_id"]) if not raw_df.empty else ["RAW-101"]
        
        edited_bom = st.data_editor(
            df_bom_all,
            column_config={
                "parent_id": st.column_config.SelectboxColumn("מק\"ט מוצר מוגמר (FG)", options=fg_ids, required=True),
                "component_id": st.column_config.SelectboxColumn("מק\"ט חומר גלם (RAW)", options=raw_ids, required=True),
                "grams_per_unit": st.column_config.NumberColumn("כמות בגרמים ליחידת מוצר (g)", min_value=0.01, format="%.2f", required=True)
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_bom"
        )
        
        if st.button("💾 שמור שינויים בעצי המוצר (BOM)"):
            conn.execute("DELETE FROM BOM")
            for _, r in edited_bom.iterrows():
                if pd.notna(r["parent_id"]) and pd.notna(r["component_id"]):
                    conn.execute("INSERT OR REPLACE INTO BOM VALUES (?, ?, ?)", (str(r["parent_id"]), str(r["component_id"]), float(r["grams_per_unit"] or 1.0)))
            conn.commit()
            st.success("כל הפורמולות ועצי המוצר עודכנו בהצלחה!")
            st.rerun()

# ==============================================================================
# מודול 3: סימולטור ותוכנית עבודה (כולל עריכת פקודות עבודה מתוך האתר)
# ==============================================================================
elif menu == "🎛️ סימולטור ותוכנית עבודה":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">🎛️ סימולטור תפעולי (MRP) וניהול תוכנית עבודה</h2>
        </div>
    """, unsafe_allow_html=True)
    
    t_sim, t_wo = st.tabs(["🧮 סימולטור דרישות חומרים ותקציב רכש", "📅 עריכת תוכנית עבודה וגאנט ייצור"])
    
    with t_sim:
        fg_df = pd.read_sql("SELECT * FROM Items WHERE category='FG'", conn)
        sim_reqs = {}
        if not fg_df.empty:
            cols = st.columns(max(1, len(fg_df)))
            for i, (_, r) in enumerate(fg_df.iterrows()):
                with cols[i]:
                    sim_reqs[r["item_id"]] = st.number_input(f"כמות יעד לסימולציה: {r['name']}", 0, 10000, 150, step=25)
                
        bom_all = pd.read_sql("SELECT * FROM BOM", conn)
        raw_all = pd.read_sql("SELECT * FROM Items WHERE category='RAW'", conn)
        sim_rows = []
        for _, raw in raw_all.iterrows():
            needed_g = 0
            for fg_id, qty in sim_reqs.items():
                m = bom_all[(bom_all["parent_id"] == fg_id) & (bom_all["component_id"] == raw["item_id"])]
                if not m.empty:
                    needed_g += qty * m.iloc[0]["grams_per_unit"]
            short_g = max(0.0, needed_g - raw["stock_grams"])
            sim_rows.append({
                "מק\"ט": raw["item_id"], "שם חומר גלם": raw["name"], "מיקום": raw["warehouse_bin"],
                "נדרש לסימולציה (גרם)": round(needed_g, 1),
                "נדרש לסימולציה (ק\"ג)": round(needed_g / 1000.0, 3),
                "קיים במלאי (ק\"ג)": round(raw["stock_grams"] / 1000.0, 3),
                "חוסר לרכש (ק\"ג)": round(short_g / 1000.0, 3),
                "עלות השלמת חוסר (₪)": round((short_g / 1000.0) * raw["cost_per_kg"], 1)
            })
        df_sim_res = pd.DataFrame(sim_rows)
        if not df_sim_res.empty:
            st.metric("סה\"כ תקציב רכש נדרש להשלמת חוסרים בסימולציה", f"₪{df_sim_res['עלות השלמת חוסר (₪)'].sum():,.1f}")
            st.dataframe(df_sim_res, use_container_width=True, hide_index=True)

    with t_wo:
        st.subheader("ניהול ועריכת פקודות עבודה (תוכנית עבודה)")
        df_wo = pd.read_sql("SELECT * FROM WorkOrders", conn)
        fg_ids = list(pd.read_sql("SELECT item_id FROM Items WHERE category='FG'", conn)["item_id"]) or ["FG-201"]
        
        edited_wo = st.data_editor(
            df_wo,
            column_config={
                "wo_id": st.column_config.NumberColumn("מס' פק\"ע", disabled=True),
                "item_id": st.column_config.SelectboxColumn("מק\"ט מוצר", options=fg_ids, required=True),
                "qty_ordered": st.column_config.NumberColumn("כמות לייצור (יח')", min_value=1, required=True),
                "start_date": st.column_config.TextColumn("תאריך התחלה (YYYY-MM-DD)"),
                "due_date": st.column_config.TextColumn("תאריך סיום (YYYY-MM-DD)"),
                "status": st.column_config.SelectboxColumn("סטטוס", options=["מתוכנן", "בייצור", "הושלם"]),
                "priority": st.column_config.SelectboxColumn("עדיפות", options=[1, 2, 3])
            },
            use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_wo"
        )
        if st.button("💾 שמור תוכנית עבודה"):
            conn.execute("DELETE FROM WorkOrders")
            for idx, r in edited_wo.iterrows():
                if pd.notna(r["item_id"]):
                    conn.execute("""
                        INSERT INTO WorkOrders (item_id, qty_ordered, start_date, due_date, status, priority)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (str(r["item_id"]), float(r["qty_ordered"] or 10), str(r["start_date"] or datetime.today().strftime("%Y-%m-%d")), str(r["due_date"] or datetime.today().strftime("%Y-%m-%d")), str(r["status"] or "מתוכנן"), int(r["priority"] or 2)))
            conn.commit()
            st.success("תוכנית העבודה עודכנה!")
            st.rerun()

        if not edited_wo.empty:
            df_g = edited_wo.copy()
            df_g["Task"] = df_g["item_id"] + " (" + df_g["qty_ordered"].astype(str) + " יח')"
            fig = px.timeline(df_g, x_start="start_date", x_end="due_date", y="Task", color="status", title="תרשים גאנט - תוכנית עבודה")
            fig.update_yaxes(autorange="reversed")
            st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# מודול 4: סוכן Gemini שמבצע פעולות ישירות על מסד הנתונים
# ==============================================================================
elif menu == "🤖 סוכן AI מבצע פעולות (Gemini)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">🤖 סוכן AI אקטיבי - תגיד לי מה לשנות והמערכת תבצע לבד!</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">בקש ממני להוסיף חומרי גלם, לעדכן כמויות בק"ג/גרם, לשנות מחירים, לבנות פורמולות או למחוק פריטים</p>
        </div>
    """, unsafe_allow_html=True)

    items_str = pd.read_sql("SELECT * FROM Items", conn).to_string(index=False)
    bom_str = pd.read_sql("SELECT * FROM BOM", conn).to_string(index=False)
    wo_str = pd.read_sql("SELECT * FROM WorkOrders", conn).to_string(index=False)

    agent_prompt = f"""
    אתה סוכן AI אוטונומי עם הרשאת כתיבה ישירה למסד נתונים SQLite של מערכת ERP למפעל קוסמטיקה.
    מבנה הטבלאות:
    1. Items(item_id TEXT PRIMARY KEY, name TEXT, category TEXT ['RAW'/'FG'], warehouse_bin TEXT, supplier TEXT, stock_grams REAL, safety_stock_grams REAL, cost_per_kg REAL)
    2. BOM(parent_id TEXT, component_id TEXT, grams_per_unit REAL)
    3. InventoryLog(trans_id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, item_id TEXT, trans_type TEXT, qty_change_grams REAL, target_assembly TEXT, reference TEXT)
    4. WorkOrders(wo_id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT, qty_ordered REAL, start_date TEXT, due_date TEXT, status TEXT, priority INTEGER)

    נתונים נוכחיים בטבלת Items:
    {items_str}
    נתונים נוכחיים בטבלת BOM:
    {bom_str}
    נתונים נוכחיים בטבלת WorkOrders:
    {wo_str}

    הנחיה קריטית:
    החזר תמיד אובייקט JSON תקני בלבד (ללא סימני markdown ```json) במבנה הבא:
    {{
        "reply": "הסבר ברור בעברית למשתמש על מה שביצעת במסד הנתונים או תשובה לשאלתו",
        "sql_commands": ["פקודת SQL ראשונה לביצוע", "פקודה שנייה..."]
    }}
    אם המשתמש מבקש להוסיף/לערוך/למחוק פריט, מלאי, עץ מוצר או פקודת עבודה - כתוב את פקודות ה-SQL המתאימות בתוך sql_commands.
    זכור: כל הכמויות של חומרי גלם (RAW) בטבלת Items נשמרות בגרמים (stock_grams). אם המשתמש אומר 5 ק"ג, הכנס 5000 גרם.
    """

    if "agent_history" not in st.session_state:
        st.session_state.agent_history = []

    for msg in st.session_state.agent_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("sql"):
                st.code(msg["sql"], language="sql")

    user_req = st.chat_input("כתוב לי כל פקודה: 'תוסיף 4 קילו חמאת שיאה', 'תמחק את מקט RAW-105', 'תבנה פורמולה למוצר חדש'...")
    if user_req:
        st.session_state.agent_history.append({"role": "user", "content": user_req})
        with st.chat_message("user"):
            st.markdown(user_req)

        if not api_key:
            st.error("הזן את ה-Gemini API Key שלך בתיבה שבסרגל הצדדי (ימין למטה) כדי שהסוכן יבצע פעולות!")
        else:
            try:
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model=selected_model,
                    contents=f"{agent_prompt}\n\nבקשת המשתמש: {user_req}"
                )
                raw_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                data = json.loads(raw_text)
                
                executed_sql = ""
                if data.get("sql_commands"):
                    for sql in data["sql_commands"]:
                        conn.execute(sql)
                    conn.commit()
                    executed_sql = "\n".join(data["sql_commands"])
                
                reply_txt = data.get("reply", "הפעולה בוצעה בהצלחה!")
                st.session_state.agent_history.append({"role": "assistant", "content": reply_txt, "sql": executed_sql})
                st.rerun()
            except Exception as e:
                st.error(f"שגיאה בביצוע הפעולה: {e}")

# ==============================================================================
# מודול 5: מרכז שליטה, גיבוי לאקסל ואיפוס נתונים מתוך האתר
# ==============================================================================
elif menu == "🛠️ הגדרות, גיבוי וניהול נתונים":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">🛠️ ניהול מסד נתונים, גיבוי לאקסל (CSV) ואיפוס מערכת</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">שליטה מלאה על כל הנתונים מתוך האתר ללא צורך בגישה לקוד</p>
        </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("📥 גיבוי וייצוא טבלאות לקובץ Excel (CSV)")
        df_all_items = pd.read_sql("SELECT * FROM Items", conn)
        st.download_button(
            "⬇️ הורד את כל טבלת הפריטים והמלאי (CSV)",
            data=df_all_items.to_csv(index=False).encode("utf-8-sig"),
            file_name="cosmetics_inventory_backup.csv",
            mime="text/csv"
        )
        df_all_log = pd.read_sql("SELECT * FROM InventoryLog", conn)
        st.download_button(
            "⬇️ הורד את יומן תנועות המלאי המלא (CSV)",
            data=df_all_log.to_csv(index=False).encode("utf-8-sig"),
            file_name="cosmetics_log_backup.csv",
            mime="text/csv"
        )

    with c2:
        st.subheader("🗑️ איפוס וניקוי נתוני דמו")
        st.caption("רוצה להתחיל עם מערכת נקייה לגמרי ולהזין רק את החומרים האמיתיים שלך?")
        if st.button("🚨 מחק את כל נתוני הדמו והתחל ממערכת ריקה"):
            conn.execute("DELETE FROM Items")
            conn.execute("DELETE FROM BOM")
            conn.execute("DELETE FROM InventoryLog")
            conn.execute("DELETE FROM WorkOrders")
            conn.commit()
            st.success("כל נתוני הדמו נמחקו! המערכת נקייה ומוכנה להזנת הפריטים שלך.")
            st.rerun()

    st.divider()
    st.subheader("💻 הרצת פקודת SQL ידנית מתוך האתר (למתקדמים)")
    custom_sql = st.text_area("כתוב שאילתת SQL (למשל UPDATE / INSERT / DELETE / SELECT):")
    if st.button("הרץ פקודת SQL"):
        try:
            if custom_sql.strip().upper().startswith("SELECT"):
                st.dataframe(pd.read_sql(custom_sql, conn), use_container_width=True)
            else:
                conn.execute(custom_sql)
                conn.commit()
                st.success("הפקודה בוצעה בהצלחה!")
        except Exception as e:
            st.error(f"שגיאת SQL: {e}")
