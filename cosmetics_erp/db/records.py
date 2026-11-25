"""Projects, alternative SKUs and shipments: tables and demo rows.

The rows are sample data so the screens have something to show. Real data can replace them
later through the database, the same way the catalog is maintained.
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta


def create_record_tables(c: sqlite3.Cursor) -> None:
    c.execute("""CREATE TABLE IF NOT EXISTS Projects (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        customer TEXT DEFAULT '',
        sku TEXT DEFAULT '',
        status TEXT DEFAULT 'Active',
        start_date TEXT DEFAULT '',
        due_date TEXT DEFAULT ''
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS AltSkus (
        alt_id INTEGER PRIMARY KEY AUTOINCREMENT,
        sku TEXT NOT NULL,
        alt_sku TEXT NOT NULL,
        description TEXT DEFAULT '',
        priority INTEGER DEFAULT 1
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS Shipments (
        shipment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        shipment_no TEXT NOT NULL,
        customer TEXT DEFAULT '',
        carrier TEXT DEFAULT '',
        ship_type TEXT DEFAULT '',
        sku TEXT DEFAULT '',
        qty_units REAL DEFAULT 0,
        ship_date TEXT DEFAULT '',
        status TEXT DEFAULT 'Planned'
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS Scenarios (
        scenario_id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner TEXT NOT NULL,
        name TEXT NOT NULL,
        shared INTEGER DEFAULT 0,
        lines TEXT DEFAULT '[]'
    )""")


def seed_record_demo(conn: sqlite3.Connection) -> None:
    """Insert demo rows, only into tables that are still empty."""
    c = conn.cursor()
    c.execute("SELECT 1 FROM Settings WHERE key = 'demo_reset_done'")
    if c.fetchone() is not None:
        return  # the owner replaced the demo data; do not load the sample rows again
    today = date.today()

    def d(days: int) -> str:
        return (today + timedelta(days=days)).isoformat()

    c.execute("SELECT COUNT(*) FROM Projects")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO Projects (code, name, customer, sku, status, start_date, due_date) VALUES (?,?,?,?,?,?,?)",
            [
                ("DEMO-001", "השקת קרם פנים היאלורוני (דוגמה)", "לקוח דמו א", "5001", "Active", d(-30), d(45)),
                ("DEMO-002", "סרום הזנה חדש (דוגמה)", "לקוח דמו ב", "5002", "Active", d(-10), d(90)),
                ("DEMO-003", "קו מתנה לחג (דוגמה)", "לקוח דמו א", "5001", "On hold", d(-60), d(20)),
                ("DEMO-004", "אריזה מחודשת לקרם (דוגמה)", "לקוח דמו ג", "5001", "Done", d(-120), d(-30)),
            ],
        )

    c.execute("SELECT COUNT(*) FROM AltSkus")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO AltSkus (sku, alt_sku, description, priority) VALUES (?,?,?,?)",
            [
                ("1001", "1001-B", "חמאת שיאה - ספק חלופי (דוגמה)", 1),
                ("1002", "1002-B", "שמן חוחובה - ספק חלופי (דוגמה)", 1),
                ("3001", "3001-ALT", "צנצנת 50ml - מפעל שני (דוגמה)", 2),
                ("5001", "5001-ALT", "קרם פנים 50ml - גרסה לחג (דוגמה)", 1),
            ],
        )

    c.execute("SELECT COUNT(*) FROM Shipments")
    if c.fetchone()[0] == 0:
        c.executemany(
            "INSERT INTO Shipments (shipment_no, customer, carrier, ship_type, sku, qty_units, ship_date, status) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [
                ("SH-1001", "לקוח דמו א", "חברת שליחים (דוגמה)", "שליח", "5001", 120, d(-3), "Delivered"),
                ("SH-1002", "לקוח דמו ב", "הובלה אווירית (דוגמה)", "אווירי", "5002", 300, d(1), "In transit"),
                ("SH-1003", "לקוח דמו ג", "הובלה ימית (דוגמה)", "ימי", "5001", 2400, d(14), "Planned"),
            ],
        )
    conn.commit()
