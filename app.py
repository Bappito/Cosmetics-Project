import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import json
from html import escape as html_escape
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

# --- הקמת מסד הנתונים (כל חומרי הגלם נשמרים בגרמים לדיוק מלא) ---
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
        WHERE b.parent_id = ? AND i.category = 'RAW'
    """
    df = pd.read_sql(query, conn, params=(parent_id,))
    if df.empty:
        return pd.DataFrame(), 0.0, 0
    
    df["נדרש לייצור (גרם)"] = df["grams_per_unit"] * target_units
    df["נדרש לייצור (ק\"ג)"] = (df["נדרש לייצור (גרם)"] / 1000.0).round(3)
    df["קיים במלאי (גרם)"] = df["stock_grams"]
    df["קיים במלאי (ק\"ג)"] = (df["stock_grams"] / 1000.0).round(3)
    df["חסר (גרם)"] = (df["נדרש לייצור (גרם)"] - df["stock_grams"]).clip(lower=0)
    df["אחוז זמינות חומר"] = ((df["stock_grams"] / df["נדרש לייצור (גרם)"]) * 100).clip(upper=100).round(1)
    df["יח' מוצר שניתן לייצר"] = (df["stock_grams"] // df["grams_per_unit"]).astype(int)
    
    return df, round(df["אחוז זמינות חומר"].mean(), 1), int(df["יח' מוצר שניתן לייצר"].min())

def render_bom_demand_table(df, period_column, is_kg):
    headers = [
        period_column, 'מק"ט אב / מוצר', 'מק"ט בן', 'שם הרכיב',
        'סוג רכיב', 'כמות ליחידה', 'כמות נדרשת'
    ]
    rows = []
    grouped = df.groupby(
        [period_column, "parent_id", "parent_name"], sort=True, dropna=False
    )
    for (period, parent_id, parent_name), components in grouped:
        components = components.sort_values(["component_id", "component_name"])
        rowspan = len(components)
        for index, (_, component) in enumerate(components.iterrows()):
            category = component["category"]
            is_raw = category == "RAW"
            unit = ("ק\"ג" if is_kg else "גרם") if is_raw else "יח'"
            divisor = 1000.0 if is_raw and is_kg else 1.0
            per_unit = component["quantity_per_unit"] / divisor
            required = component["required_quantity"] / divisor
            category_name = {
                "RAW": "חומר גלם",
                "PACKAGING": "אריזה",
                "LABEL": "מדבקה",
            }.get(category, category)
            parent_cell = ""
            if index == 0:
                parent_cell = (
                    f'<td rowspan="{rowspan}" class="parent-sku" '
                    'style="vertical-align:middle; padding:8px;">'
                    f'<strong>{html_escape(str(parent_id))}</strong><br>'
                    f'{html_escape(str(parent_name))}</td>'
                )
            rows.append(
                "<tr>"
                f"<td>{html_escape(str(period))}</td>"
                f"{parent_cell}"
                f"<td>{html_escape(str(component['component_id']))}</td>"
                f"<td>{html_escape(str(component['component_name']))}</td>"
                f"<td>{html_escape(str(category_name))}</td>"
                f"<td>{per_unit:,.3f} {unit}</td>"
                f"<td>{required:,.3f} {unit}</td>"
                "</tr>"
            )

    table_html = (
        '<div style="overflow-x:auto; direction:rtl;">'
        '<table style="width:100%; border-collapse:collapse; text-align:right;">'
        "<thead><tr>"
        + "".join(
            f'<th style="padding:8px; border-bottom:1px solid #64748b;">'
            f"{html_escape(header)}</th>"
            for header in headers
        )
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

# --- תפריט צד וחיבור Gemini API ---
st.sidebar.markdown("## 🧪 Priority Cosmetics")
menu = st.sidebar.radio(
    "ניווט במערכת:",
    [
        "📦 ניהול מלאי ותנועות (Priority)",
        "⚙️ ייצור, פורמולות ומוכנות (%)",
        "🎛️ סימולטור ותוכנית עבודה",
        "🤖 סוכן AI מבצע פעולות (Gemini)"
    ]
)

st.sidebar.divider()
unit_mode = st.sidebar.radio("⚖️ יחידת תצוגת משקל במערכת:", ["קילוגרם (kg)", "גרם (g)"])
is_kg = unit_mode.startswith("קילוגרם")

st.sidebar.divider()
api_key = st.sidebar.text_input("🔑 הזן Gemini API Key:", type="password")

# ==============================================================================
# מודול 1: ניהול מלאי קוסמטיקה, מיקומים ויומן תנועות (30 יום אחורה)
# ==============================================================================
if menu == "📦 ניהול מלאי ותנועות (Priority)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">📦 ניהול מלאי חומרי גלם ומוצרים (Priority ERP)</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">ניהול משקלים (ק"ג / גרם), מיקומי מחסן, עלויות ומעקב תנועות לאיזו הרכבה הלך כל חומר</p>
        </div>
    """, unsafe_allow_html=True)
    
    df_raw = pd.read_sql("SELECT * FROM Items WHERE category = 'RAW'", conn)
    df_raw["שווי מלאי (₪)"] = (df_raw["stock_grams"] / 1000.0) * df_raw["cost_per_kg"]
    
    k1, k2, k3 = st.columns(3)
    k1.metric("סה\"כ חומרי גלם במערכת", len(df_raw))
    k2.metric("משקל חומרי גלם כולל במחסן", f"{df_raw['stock_grams'].sum()/1000:,.2f} ק\"ג" if is_kg else f"{df_raw['stock_grams'].sum():,.0f} גרם")
    k3.metric("שווי כספי של חומרי הגלם", f"₪{df_raw['שווי מלאי (₪)'].sum():,.0f}")

    tab1, tab2, tab3 = st.tabs([
        "📋 טבלת מלאי חיה (עריכה והוספה מתוך האתר)",
        "🔄 דיווח תנועת מלאי / ניפוק להרכבה",
        "🕒 היסטוריית תנועות מלאי (30 יום אחורה - לאיזה ייצור הלך החומר)"
    ])
    
    with tab1:
        factor = 1000.0 if is_kg else 1.0
        unit_label = "ק\"ג" if is_kg else "גרם"
        
        st.subheader(f"מלאי חומרי גלם נוכחי ( מוצג ב-{unit_label} )")
        st.caption("💡 תוכל לשנות כל כמות, מחיר או מיקום במחסן בדאבל-קליק ישירות בטבלה, או להוסיף שורה חדשה בתחתית הטבלה וללחוץ על שמירה.")
        
        df_disp = df_raw.copy()
        df_disp["display_stock"] = (df_disp["stock_grams"] / factor).round(3)
        df_disp["display_safety"] = (df_disp["safety_stock_grams"] / factor).round(3)
        df_disp["שווי כמות נוכחית (₪)"] = ((df_disp["stock_grams"] / 1000.0) * df_disp["cost_per_kg"]).round(1)
        
        edited = st.data_editor(
            df_disp[["item_id", "name", "warehouse_bin", "supplier", "display_stock", "display_safety", "cost_per_kg", "שווי כמות נוכחית (₪)"]],
            column_config={
                "item_id": st.column_config.TextColumn("מק\"ט", required=True),
                "name": st.column_config.TextColumn("שם חומר הגלם", required=True),
                "warehouse_bin": st.column_config.TextColumn("מיקום במחסן"),
                "supplier": st.column_config.TextColumn("ספק"),
                "display_stock": st.column_config.NumberColumn(f"מלאי נוכחי ({unit_label})", format="%.3f" if is_kg else "%.0f"),
                "display_safety": st.column_config.NumberColumn(f"מלאי ביטחון ({unit_label})", format="%.3f" if is_kg else "%.0f"),
                "cost_per_kg": st.column_config.NumberColumn("מחיר ל-1 ק\"ג (₪)", format="₪%.2f"),
                "שווי כמות נוכחית (₪)": st.column_config.NumberColumn("שווי המלאי (₪)", disabled=True, format="₪%.1f")
            },
            use_container_width=True, hide_index=True, num_rows="dynamic"
        )
        
        if st.button("💾 שמור שינויים בטבלת המלאי"):
            for _, r in edited.iterrows():
                if r["item_id"] and r["name"]:
                    s_grams = float(r["display_stock"] or 0) * factor
                    safe_grams = float(r["display_safety"] or 0) * factor
                    conn.execute("""
                        INSERT OR REPLACE INTO Items (item_id, name, category, warehouse_bin, supplier, stock_grams, safety_stock_grams, cost_per_kg)
                        VALUES (?, ?, 'RAW', ?, ?, ?, ?, ?)
                    """, (r["item_id"], r["name"], r["warehouse_bin"] or "A-01", r["supplier"] or "כללי", s_grams, safe_grams, float(r["cost_per_kg"] or 0)))
            conn.commit()
            st.success("המלאי עודכן בהצלחה!")
            st.rerun()

    with tab2:
        st.subheader("עדכון תנועת מלאי (קליטת סחורה / ניפוק להרכבה)")
        c1, c2 = st.columns(2)
        with c1:
            sel_raw = st.selectbox("בחר חומר גלם:", df_raw["item_id"] + " - " + df_raw["name"])
            t_type = st.selectbox("סוג פעולה:", ["📤 ניפוק להרכבה / ייצור (-)", "📥 קבלת חומר גלם מספק (+)", "⚖️ ספירת מלאי (קביעת יתרה)"])
            t_unit = st.radio("הזן כמות ב:", ["גרם (g)", "קילוגרם (kg)"], horizontal=True)
            t_val = st.number_input("כמות לתנועה:", min_value=0.0, value=250.0, step=10.0)
        with c2:
            fg_list = pd.read_sql("SELECT item_id, name FROM Items WHERE category='FG'", conn)
            target_assm = st.selectbox("שיוך להרכבה / מוצר (לאן הלך החומר):", ["מלאי כללי / מחסן"] + list(fg_list["item_id"] + " - " + fg_list["name"]))
            ref_txt = st.text_input("מספר אצווה (Batch) / תעודת משלוח / הערה:", value="Batch-105")
            
            if st.button("בצע עדכון מלאי"):
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
                st.success(f"המלאי עודכן ונרשם ביומן! יתרה חדשה: {new_g:,.0f} גרם ({new_g/1000:,.2f} ק\"ג)")
                st.rerun()

    with tab3:
        st.subheader("מעקב תנועות מלאי (30 יום אחורה) - לאיזו הרכבה הלך כל חומר")
        cutoff_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        query_log = """
            SELECT l.trans_id AS "מס'", l.trans_date AS "תאריך ושעה", l.item_id AS "מק""ט",
                   i.name AS "שם חומר גלם", l.trans_type AS "סוג תנועה",
                   l.qty_change_grams AS "שינוי בגרמים (g)",
                   ROUND(l.qty_change_grams / 1000.0, 3) AS "שינוי בק""ג (kg)",
                   l.target_assembly AS "שויך להרכבה / מוצר", l.reference AS "אצווה / אסמכתא"
            FROM InventoryLog l
            LEFT JOIN Items i ON l.item_id = i.item_id
            WHERE l.trans_date >= ?
            ORDER BY l.trans_id DESC
        """
        df_log = pd.read_sql(query_log, conn, params=(cutoff_date,))
        filter_item_log = st.selectbox("סנן היסטוריה לפי חומר גלם:", ["הצג את כל התנועות"] + list(df_raw["item_id"] + " - " + df_raw["name"]))
        if filter_item_log != "הצג את כל התנועות":
            f_code = filter_item_log.split(" - ")[0]
            df_log = df_log[df_log["מק\"ט"] == f_code]
        st.dataframe(df_log, use_container_width=True, hide_index=True)

# ==============================================================================
# מודול 2: ניהול ייצור, בניית עצי מוצר בגרמים ואחוז מוכנות חומר
# ==============================================================================
elif menu == "⚙️ ייצור, פורמולות ומוכנות (%)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">⚙️ ניהול ייצור, בניית עצי מוצר (בגרמים) ואחוז חומר מהמלאי</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">בניית פורמולות קוסמטיות בגרמים, צפייה באחוז החומר הזמין במלאי לכל מוצר ודיווח אצוות ייצור</p>
        </div>
    """, unsafe_allow_html=True)

    fg_df = pd.read_sql("SELECT * FROM Items WHERE category='FG'", conn)

    tab_readiness, tab_bom_builder = st.tabs([
        "📊 אחוז מוכנות חומרים מהמלאי וייצור אצוות",
        "🧪 בניית ועריכת עצי מוצר (חומרי גלם, אריזות ומדבקות)"
    ])

    with tab_readiness:
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
        st.dataframe(df_kit, use_container_width=True, hide_index=True)

        if st.button(f"✅ בצע ייצור של {batch_size} יח' ממוצר {sel_fg_code} (גרע גרמים מהמלאי ורשום ביומן התנועות)"):
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

    with tab_bom_builder:
        st.subheader("בנייה ועדכון של עצי מוצר מתוך האתר")
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            st.markdown("#### 1. הוסף / עדכן רכיב בעץ מוצר")
            target_fg = st.selectbox("בחר מוצר מוגמר:", fg_df["item_id"] + " - " + fg_df["name"], key="bom_fg")
            component_df = pd.read_sql(
                "SELECT item_id, name, category FROM Items "
                "WHERE category IN ('RAW', 'PACKAGING', 'LABEL') ORDER BY item_id",
                conn
            )
            target_component = st.selectbox(
                "בחר חומר גלם, אריזה או מדבקה להוספה לעץ המוצר:",
                component_df["item_id"] + " - " + component_df["name"],
                key="bom_component"
            )
            quantity_val = st.number_input(
                "כמות רכיב הנדרשת ליחידת מוצר אחת (גרמים לחומר גלם, יחידות לאריזה/מדבקה):",
                min_value=0.1, value=10.0, step=0.5
            )
            if st.button("שמור רכיב בעץ המוצר"):
                p_id = target_fg.split(" - ")[0]
                c_id = target_component.split(" - ")[0]
                conn.execute("INSERT OR REPLACE INTO BOM VALUES (?, ?, ?)", (p_id, c_id, quantity_val))
                conn.commit()
                st.success("עץ המוצר עודכן!")
                st.rerun()
        with c_b2:
            st.markdown("#### 2. הקמת מוצר קוסמטי מוגמר חדש (FG)")
            new_fg_id = st.text_input("מק\"ט מוצר חדש (למשל FG-205):")
            new_fg_name = st.text_input("שם המוצר הקוסמטי:")
            if st.button("הקם מוצר חדש"):
                if new_fg_id and new_fg_name:
                    conn.execute("INSERT OR REPLACE INTO Items VALUES (?, ?, 'FG', 'FG-Z1', 'ייצור עצמי', 0, 10, 0)", (new_fg_id, new_fg_name))
                    conn.commit()
                    st.success("המוצר הוקם! כעת תוכל לשייך לו חומרי גלם, אריזות ומדבקות.")
                    st.rerun()
            st.markdown("#### 3. הוסף פריט אריזה או מדבקה")
            new_component_id = st.text_input("מק\"ט אריזה/מדבקה:", key="new_component_id")
            new_component_name = st.text_input("שם האריזה/המדבקה:", key="new_component_name")
            new_component_category = st.selectbox(
                "סוג הפריט:",
                ["PACKAGING", "LABEL"],
                format_func=lambda value: "אריזה" if value == "PACKAGING" else "מדבקה",
                key="new_component_category"
            )
            if st.button("הוסף אריזה/מדבקה"):
                if new_component_id and new_component_name:
                    existing_component = conn.execute(
                        "SELECT 1 FROM Items WHERE item_id = ?", (new_component_id,)
                    ).fetchone()
                    if existing_component:
                        st.error("מק\"ט זה כבר קיים במערכת.")
                    else:
                        conn.execute(
                            """INSERT INTO Items
                            (item_id, name, category, warehouse_bin, supplier, stock_grams,
                             safety_stock_grams, cost_per_kg)
                            VALUES (?, ?, ?, 'PACK-Z1', 'ספק כללי', 0, 0, 0)""",
                            (new_component_id, new_component_name, new_component_category)
                        )
                        conn.commit()
                        st.success("הפריט נוסף למערכת; כעת ניתן לשייך אותו לעץ מוצר.")
                        st.rerun()

# ==============================================================================
# מודול 3: סימולטור ותוכנית עבודה
# ==============================================================================
elif menu == "🎛️ סימולטור ותוכנית עבודה":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">🎛️ סימולטור תפעולי (MRP בגרמים/ק"ג) ותוכנית עבודה</h2>
        </div>
    """, unsafe_allow_html=True)
    
    fg_df = pd.read_sql("SELECT * FROM Items WHERE category='FG'", conn)
    sim_reqs = {}
    cols = st.columns(max(1, len(fg_df)))
    for i, (_, r) in enumerate(fg_df.iterrows()):
        with cols[i]:
            sim_reqs[r["item_id"]] = st.number_input(f"כמות יעד לסימולציה: {r['name']}", 0, 5000, 150, step=25)
            
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
            "נדרש לסימולציה (ק\"ג)": round(needed_g / 1000.0, 2),
            "קיים במלאי (ק\"ג)": round(raw["stock_grams"] / 1000.0, 2),
            "חוסר לרכש (ק\"ג)": round(short_g / 1000.0, 2),
            "עלות השלמת חוסר (₪)": round((short_g / 1000.0) * raw["cost_per_kg"], 1)
        })
    st.dataframe(pd.DataFrame(sim_rows), use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("נגזרת עצי מוצר לפי חודשים ושבועות (חומרי גלם, אריזות ומדבקות)")
    st.caption(
        "הדרישות מחושבות מהזמנות הייצור הקיימות לפי תאריך היעד שלהן. "
        "חומרי גלם מוצגים בגרם/ק״ג, ואריזות ומדבקות ביחידות."
    )
    demand_df = pd.read_sql(
        """
        SELECT w.item_id AS parent_id, parent.name AS parent_name,
               w.qty_ordered, w.due_date, b.component_id,
               component.name AS component_name, component.category,
               b.grams_per_unit AS quantity_per_unit
        FROM WorkOrders w
        JOIN Items parent ON parent.item_id = w.item_id
        JOIN BOM b ON b.parent_id = w.item_id
        JOIN Items component ON component.item_id = b.component_id
        WHERE w.status IN ('בייצור', 'מתוכנן')
        """,
        conn
    )
    if demand_df.empty:
        st.info("אין כרגע הזמנות ייצור פעילות עם רכיבים בעץ מוצר.")
    else:
        demand_df["due_date"] = pd.to_datetime(demand_df["due_date"], errors="coerce")
        missing_dates = int(demand_df["due_date"].isna().sum())
        if missing_dates:
            st.warning(f"{missing_dates} שורות ללא תאריך יעד תקין לא נכללו בדוח.")
        demand_df = demand_df.dropna(subset=["due_date"]).copy()
        if demand_df.empty:
            st.info("אין הזמנות פעילות עם תאריך יעד תקין להצגה.")
        else:
            demand_df["חודש"] = demand_df["due_date"].dt.strftime("%Y-%m")
            demand_df["שבוע"] = demand_df["due_date"].dt.strftime("%G-W%V")
            demand_df["required_quantity"] = (
                demand_df["qty_ordered"] * demand_df["quantity_per_unit"]
            )
            aggregation_columns = [
                "parent_id", "parent_name", "component_id", "component_name",
                "category", "quantity_per_unit"
            ]
            monthly_demand = demand_df.groupby(
                ["חודש"] + aggregation_columns, as_index=False
            )["required_quantity"].sum()
            weekly_demand = demand_df.groupby(
                ["שבוע"] + aggregation_columns, as_index=False
            )["required_quantity"].sum()
            month_tab, week_tab = st.tabs(["לפי חודש", "לפי שבוע"])
            with month_tab:
                render_bom_demand_table(monthly_demand, "חודש", is_kg)
            with week_tab:
                render_bom_demand_table(weekly_demand, "שבוע", is_kg)

# ==============================================================================
# מודול 4: סוכן Gemini שמבצע פעולות ישירות על מסד הנתונים (Autonomous SQL Agent)
# ==============================================================================
elif menu == "🤖 סוכן AI מבצע פעולות (Gemini)":
    st.markdown("""
        <div class="priority-header">
            <h2 style="margin:0;">🤖 סוכן AI אקטיבי - תגיד לי מה לשנות והמערכת תבצע לבד!</h2>
            <p style="margin:4px 0 0 0; opacity:0.85;">בקש ממני להוסיף חומרי גלם, לעדכן כמויות בק"ג/גרם, לבנות עצי מוצר או לרשום תנועות – ואני אבצע את הפקודה ב-SQL</p>
        </div>
    """, unsafe_allow_html=True)

    items_str = pd.read_sql("SELECT * FROM Items", conn).to_string(index=False)
    bom_str = pd.read_sql("SELECT * FROM BOM", conn).to_string(index=False)

    agent_prompt = f"""
    אתה סוכן AI אוטונומי עם הרשאת כתיבה ישירה למסד נתונים SQLite של מערכת ERP למפעל קוסמטיקה.
    מבנה הטבלאות:
    1. Items(item_id TEXT PRIMARY KEY, name TEXT, category TEXT ['RAW'/'FG'], warehouse_bin TEXT, supplier TEXT, stock_grams REAL, safety_stock_grams REAL, cost_per_kg REAL)
    2. BOM(parent_id TEXT, component_id TEXT, grams_per_unit REAL)
    3. InventoryLog(trans_id INTEGER PRIMARY KEY AUTOINCREMENT, trans_date TEXT, item_id TEXT, trans_type TEXT, qty_change_grams REAL, target_assembly TEXT, reference TEXT)

    נתונים נוכחיים בטבלת Items:
    {items_str}
    נתונים נוכחיים בטבלת BOM:
    {bom_str}

    הנחיה קריטית:
    החזר תמיד אובייקט JSON תקני בלבד (ללא סימני markdown ```json) במבנה הבא:
    {{
        "reply": "הסבר קצר וידידותי בעברית למשתמש על מה שעשית או תשובה לשאלתו",
        "sql_commands": ["פקודת SQL ראשונה לביצוע אם המשתמש ביקש לשנות/להוסיף/למחוק נתונים", "פקודה שנייה..."]
    }}
    אם המשתמש רק שואל שאלה בלי לבקש שינוי בנתונים, החזר רשימה ריקה ב-sql_commands: [].
    זכור: כל הכמויות של חומרי גלם (RAW) בטבלת Items נשמרות בגרמים (stock_grams). אם המשתמש אומר 5 ק"ג, הכנס 5000 גרם.
    """

    user_req = st.chat_input("כתוב לי פקודה, למשל: 'תוסיף 3 קילו חמאת שיאה למלאי' או 'תקים חומר גלם חדש שמן קוקוס מקט RAW-109'...")
    if user_req:
        if not api_key:
            st.error("הזן את ה-Gemini API Key שלך בתיבה שבסרגל הצדדי (ימין למטה) כדי שאוכל לבצע פעולות!")
        else:
            try:
                client = genai.Client(api_key=api_key)
                resp = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=f"{agent_prompt}\n\nבקשת המשתמש: {user_req}"
                )
                raw_text = resp.text.strip().replace("```json", "").replace("```", "").strip()
                data = json.loads(raw_text)
                
                if data.get("sql_commands"):
                    for sql in data["sql_commands"]:
                        conn.execute(sql)
                    conn.commit()
                    st.success("⚡ הפעולה בוצעה אוטומטית במסד הנתונים!")
                    st.code("\n".join(data["sql_commands"]), language="sql")
                st.info(data.get("reply", "בוצע!"))
            except Exception as e:
                st.error(f"שגיאה בביצוע הפעולה: {e}")
