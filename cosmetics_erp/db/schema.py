import sqlite3
from datetime import datetime, timedelta



def _demo_reset_done(c) -> bool:
    """True once the owner has replaced the demo data, so the demo rows are never loaded again."""
    c.execute("SELECT 1 FROM Settings WHERE key = 'demo_reset_done'")
    return c.fetchone() is not None


def init_db(conn: sqlite3.Connection):
    """Create the tables and the demo data if they are missing. Safe to run on every start."""
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

    c.execute("""CREATE TABLE IF NOT EXISTS AuditLog (
        audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
        at TEXT,
        scope TEXT,
        action TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS Settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    from cosmetics_erp.services.planning import PLAN_START_KEY, current_plan_start

    c.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES (?, ?)",
              (PLAN_START_KEY, current_plan_start().isoformat()))
    conn.commit()  # release the write lock right away; other connections need it

    c.execute("SELECT COUNT(*) FROM Catalog")
    if c.fetchone()[0] == 0 and not _demo_reset_done(c):
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
    # Colour warehouse: hair-colour raw materials. They are RAW items stored in WH_COLOR,
    # so they are bought, planned and consumed like other raw materials. Added on
    # existing databases too, but only when no colour items exist yet.
    c.execute("SELECT COUNT(*) FROM Catalog WHERE primary_warehouse = 'WH_COLOR'")
    if c.fetchone()[0] == 0 and not _demo_reset_done(c):
        color_items = [
            ("6001", "צבע שיער 4.0 חום (דוגמה)", "RAW", 0.0, 5000.0, "0", "-", "ספק צבעים (דוגמה)", "-", "2026-11-10 (+5 ק\"ג)", 60.0, 1.0, 58.0, "WH_COLOR", "SAP-6001"),
            ("6002", "צבע שיער 6.0 חום כהה (דוגמה)", "RAW", 0.0, 9000.0, "0", "-", "ספק צבעים (דוגמה)", "-", "2026-11-10 (+9 ק\"ג)", 62.0, 1.0, 60.0, "WH_COLOR", "SAP-6002"),
            ("6003", "צבע שיער 7.1 בלונד אפר (דוגמה)", "RAW", 0.0, 4000.0, "0", "-", "ספק צבעים (דוגמה)", "-", "2026-11-09 (+4 ק\"ג)", 75.0, 1.0, 72.0, "WH_COLOR", "SAP-6003"),
            ("6004", "צבע שיער 9.3 בלונד זהוב בהיר (דוגמה)", "RAW", 0.0, 3000.0, "0", "-", "ספק צבעים (דוגמה)", "-", "2026-11-09 (+3 ק\"ג)", 78.0, 1.0, 75.0, "WH_COLOR", "SAP-6004"),
            ("6005", "מחמצן 6% / אוקסידנט (דוגמה)", "RAW", 0.0, 12000.0, "0", "-", "ספק צבעים (דוגמה)", "-", "2026-11-11 (+12 ק\"ג)", 25.0, 2.0, 23.0, "WH_COLOR", "SAP-6005"),
        ]
        c.executemany("INSERT INTO Catalog VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", color_items)
        today_dt = datetime.today()
        for item in color_items:
            b_sku, b_wg = item[0], item[4]
            c.execute("""
                INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, source, status)
                VALUES (?,?,0,?,?,?,'OPENING','Active')
            """, (b_sku, f"OPEN-{b_sku}", b_wg,
                  (today_dt + timedelta(days=730)).strftime("%Y-%m-%d"), today_dt.strftime("%Y-%m-%d")))
        conn.commit()
    from cosmetics_erp.db.records import create_record_tables, seed_record_demo
    create_record_tables(c)
    seed_record_demo(conn)
    # The connection is shared across reruns (see db/connection.py), so it must not be closed here.
