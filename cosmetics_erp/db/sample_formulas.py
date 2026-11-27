"""Sample data: four cosmetic formulas with pack sizes, a production plan and purchase orders.

All of it is invented demo information. Formulas are kg per 1000 kg of bulk, which equals grams
per kg of bulk. Each pack size is its own finished product with its own tree (bulk plus packaging).
Load it with ``python manage.py load_sample_data``. The hair-colour warehouse is left as it is.
"""
from __future__ import annotations

import math
import sqlite3
from datetime import date, datetime, timedelta

from cosmetics_erp.db.schema import init_db
from cosmetics_erp.services.planning import PLAN_START_KEY, current_plan_start

# key: (Hebrew, English, price per kg, supplier, minimum order kg)
RAW = {
    "aqua": ("מים מזוקקים", "Aqua", 0.0, "מערכת מים פנימית", 1),
    "ceteareth25": ("צטארת-25", "Ceteareth-25", 28, "כימדע", 25),
    "peg7": ("פוליאתילן גליקול-7 גליצריל קוקואט", "PEG-7 Glyceryl Cocoate", 32, "כימדע", 25),
    "glycerin": ("גליצרין צמחי", "Glycerin", 14, "כימדע", 50),
    "beeswax": ("שעוות דבורים", "Beeswax (Cera Alba)", 65, "נטורל אוילס", 25),
    "jojoba": ("שמן חוחובה", "Simmondsia Chinensis Seed Oil", 140, "נטורל אוילס", 10),
    "cetearyl": ("צטאריל אלכוהול", "Cetearyl Alcohol", 22, "פארמה-כם", 25),
    "pvp": ("פוליויניל פירולידון (PVP)", "Polyvinylpyrrolidone", 55, "פארמה-כם", 10),
    "fragrance": ("תמצית בישום", "Fragrance (Parfum)", 180, "בוטניקה סחר", 5),
    "preservative": ("פנוקסיאתנול ואתיל-הקסילגליצרין", "Phenoxyethanol & Ethylhexylglycerin", 70, "פארמה-כם", 10),
    "vitamin_e": ("ויטמין E", "Tocopherol", 220, "כימדע", 1),
    "sles": ("סודיום לאורת סולפט", "SLES 70%", 12, "כימדע", 200),
    "capb": ("קוקמידופרופיל בטאין", "Cocamidopropyl Betaine", 16, "כימדע", 100),
    "decyl": ("דציל גלוקוזיד", "Decyl Glucoside", 24, "פארמה-כם", 50),
    "salt": ("סודיום כלוריד", "Sodium Chloride", 3, "כימדע", 25),
    "pq7": ("פוליקווטרניום-7", "Polyquaternium-7", 30, "פארמה-כם", 10),
    "hyaluronate": ("חומצה היאלורונית", "Sodium Hyaluronate", 1200, "פארמה-כם", 1),
    "citric": ("חומצת לימון", "Citric Acid", 12, "כימדע", 5),
    "edta": ("דיסודיום EDTA", "Disodium EDTA", 35, "כימדע", 5),
    "cetyl": ("צטיל אלכוהול", "Cetyl Alcohol", 24, "פארמה-כם", 25),
    "behentrimonium": ("בהנטרימוניום כלוריד", "Behentrimonium Chloride", 60, "פארמה-כם", 25),
    "cetrimonium": ("צטרימוניום כלוריד", "Cetrimonium Chloride", 25, "פארמה-כם", 25),
    "argan": ("שמן ארגן", "Argania Spinosa Kernel Oil", 190, "נטורל אוילס", 10),
    "shea": ("חמאת שיאה", "Butyrospermum Parkii Butter", 85, "נטורל אוילס", 25),
    "dimethicone": ("דימתיקון", "Dimethicone", 38, "כימדע", 25),
    "panthenol": ("פנתנול - ויטמין B5", "Panthenol", 95, "פארמה-כם", 5),
    "caprylic": ("טריגליצריד קפרילי/קפרי", "Caprylic/Capric Triglyceride", 40, "בוטניקה סחר", 25),
    "gms": ("גליצריל סטארט", "Glyceryl Stearate", 26, "בוטניקה סחר", 25),
    "almond": ("שמן שקדים מתוקים", "Prunus Amygdalus Dulcis Oil", 55, "נטורל אוילס", 10),
}
RAW_SKU = {key: str(1001 + i) for i, key in enumerate(RAW)}

# bulk SKU: (Hebrew, English, bulk stock kg, weekly production kg W1..W8, formula kg per 1000 kg)
BULK = {
    "2001": ("ווקס חוחובה לשיער", "Jojoba Hair Wax", 100, [0, 0, 150, 0, 0, 100, 0, 0], {
        "aqua": 485, "ceteareth25": 220, "peg7": 70, "glycerin": 60, "beeswax": 50, "jojoba": 45,
        "cetearyl": 30, "pvp": 20, "fragrance": 10, "preservative": 8, "vitamin_e": 2}),
    "2002": ("שמפו היאלורוני", "Hyaluronic Shampoo", 800, [500, 500, 0, 500, 500, 0, 500, 500], {
        "aqua": 684.5, "sles": 160, "capb": 65, "decyl": 30, "glycerin": 25, "salt": 12, "pq7": 8,
        "preservative": 7, "fragrance": 4, "hyaluronate": 2, "citric": 1.5, "edta": 1}),
    "2003": ("מסכת שיער היאלורונית", "Hyaluronic Hair Mask", 400, [0, 0, 500, 500, 0, 0, 500, 0], {
        "aqua": 794, "cetyl": 45, "behentrimonium": 35, "glycerin": 30, "cetrimonium": 25, "argan": 20,
        "shea": 15, "dimethicone": 15, "preservative": 8, "fragrance": 6, "hyaluronate": 3.5,
        "panthenol": 2, "citric": 1.5}),
    "2004": ("קרם ידיים", "Hand Cream", 80, [100, 0, 100, 0, 100, 0, 100, 0], {
        "aqua": 736, "glycerin": 60, "cetearyl": 45, "shea": 40, "caprylic": 35, "gms": 25, "almond": 20,
        "dimethicone": 15, "panthenol": 10, "preservative": 8, "fragrance": 4, "vitamin_e": 2}),
}

# packaging SKU: (Hebrew, English, price per unit, supplier)
PKG = {
    "3001": ("בקבוק 500 מ\"ל לשמפו", "Shampoo bottle 500 ml", 1.9, "אריזות המרכז"),
    "3002": ("בקבוק 1 ליטר לשמפו", "Shampoo bottle 1 L", 2.8, "אריזות המרכז"),
    "3003": ("משאבה לבקבוק שמפו", "Shampoo bottle pump", 0.9, "אריזות המרכז"),
    "3004": ("צנצנת 500 מ\"ל למסכה", "Mask jar 500 ml", 2.4, "גלאס-פק"),
    "3005": ("צנצנת 1 ליטר למסכה", "Mask jar 1 L", 3.5, "גלאס-פק"),
    "3006": ("מכסה לצנצנת 500 מ\"ל", "Lid for 500 ml jar", 0.7, "גלאס-פק"),
    "3007": ("מכסה לצנצנת 1 ליטר", "Lid for 1 L jar", 0.9, "גלאס-פק"),
    "3008": ("קופסה 100 מ\"ל לווקס", "Wax tin 100 ml", 1.6, "אריזות המרכז"),
    "3009": ("מכסה לקופסת ווקס", "Wax tin lid", 0.5, "אריזות המרכז"),
    "3010": ("שפופרת 100 מ\"ל לקרם ידיים", "Hand cream tube 100 ml", 1.1, "אריזות המרכז"),
    "3011": ("פקק לשפופרת", "Tube cap", 0.3, "אריזות המרכז"),
    "3012": ("מדבקה - ווקס 100 מ\"ל", "Label - wax 100 ml", 0.35, "דפוס מדבקות"),
    "3013": ("מדבקה - שמפו 500 מ\"ל", "Label - shampoo 500 ml", 0.35, "דפוס מדבקות"),
    "3014": ("מדבקה - שמפו 1 ליטר", "Label - shampoo 1 L", 0.4, "דפוס מדבקות"),
    "3015": ("מדבקה - מסכה 500 מ\"ל", "Label - mask 500 ml", 0.35, "דפוס מדבקות"),
    "3016": ("מדבקה - מסכה 1 ליטר", "Label - mask 1 L", 0.4, "דפוס מדבקות"),
    "3017": ("מדבקה - קרם ידיים 100 מ\"ל", "Label - hand cream 100 ml", 0.3, "דפוס מדבקות"),
}

# finished product SKU: (Hebrew, English, selling price, stock units, weekly units, bulk SKU, grams per unit, packaging)
FG = {
    "5001": ("ווקס חוחובה לשיער 100 מ\"ל", "Jojoba Hair Wax 100 ml", 35, 150,
             [300, 280, 320, 300, 300, 260, 340, 300], "2001", 100, ["3008", "3009", "3012"]),
    "5002": ("שמפו היאלורוני 500 מ\"ל", "Hyaluronic Shampoo 500 ml", 29, 600,
             [400, 380, 420, 400, 440, 360, 400, 400], "2002", 500, ["3001", "3003", "3013"]),
    "5003": ("שמפו היאלורוני 1 ליטר", "Hyaluronic Shampoo 1 L", 45, 250,
             [150, 140, 160, 150, 160, 140, 150, 150], "2002", 1000, ["3002", "3003", "3014"]),
    "5004": ("מסכת שיער היאלורונית 500 מ\"ל", "Hyaluronic Hair Mask 500 ml", 49, 300,
             [200, 180, 220, 200, 200, 180, 220, 200], "2003", 500, ["3004", "3006", "3015"]),
    "5005": ("מסכת שיער היאלורונית 1 ליטר", "Hyaluronic Hair Mask 1 L", 79, 120,
             [80, 70, 90, 80, 80, 70, 90, 80], "2003", 1000, ["3005", "3007", "3016"]),
    "5006": ("קרם ידיים 100 מ\"ל", "Hand Cream 100 ml", 25, 400,
             [300, 320, 280, 300, 300, 320, 280, 300], "2004", 100, ["3010", "3011", "3017"]),
}

# Materials whose stock is deliberately low, so the planning screens show every readiness colour.
RAW_STOCK_KG = {"aqua": 1_000_000, "sles": 200, "beeswax": 8, "behentrimonium": 40, "edta": 2, "argan": 15}
PKG_STOCK = {"3001": 2000, "3010": 1500}

ALTERNATIVES = [("jojoba", "שמן חוחובה - ספק חלופי (דוגמה)"), ("shea", "חמאת שיאה - ספק חלופי (דוגמה)"),
                ("3001", "בקבוק 500 מ\"ל - ספק חלופי (דוגמה)")]

# Purchase orders in every situation the planning screens can show:
# (number, material key or packaging SKU, quantity in kg or units, days, counted from, status).
# "today" keeps late and due-today orders true on any day; "plan" places the rest in a plan week.
ORDERS = [
    ("PO-101", "hyaluronate", 5, 1, "today", "In Transit"),
    ("PO-102", "beeswax", 25, 9, "plan", "In Transit"),
    ("PO-103", "sles", 500, 23, "plan", "In Transit"),
    ("PO-104", "3001", 3000, 23, "plan", "In Transit"),
    ("PO-105", "argan", 20, 30, "plan", "In Transit"),
    ("PO-106", "3010", 2000, 30, "plan", "In Transit"),
    ("PO-107", "behentrimonium", 50, 37, "plan", "In Transit"),
    # late: due before today and not received
    ("PO-108", "glycerin", 100, -9, "today", "In Transit"),
    ("PO-120", "3008", 1000, -3, "today", "Confirmed"),
    # due today
    ("PO-109", "hyaluronate", 2, 0, "today", "Confirmed"),
    ("PO-119", "3013", 2000, 0, "today", "In Transit"),
    # weeks 2-3
    ("PO-110", "ceteareth25", 50, 10, "plan", "Confirmed"),
    ("PO-118", "3004", 500, 9, "plan", "In Transit"),
    ("PO-111", "capb", 200, 17, "plan", "In Transit"),
    ("PO-122", "3010", 500, 16, "plan", "Confirmed"),
    # weeks 5-8, some still drafts
    ("PO-115", "fragrance", 10, 31, "plan", "Draft"),
    ("PO-117", "3001", 1500, 38, "plan", "Confirmed"),
    ("PO-121", "3003", 2000, 37, "plan", "Draft"),
    ("PO-112", "edta", 0.3, 43, "plan", "In Transit"),  # too small: still short after it arrives
    ("PO-114", "sles", 300, 43, "plan", "Confirmed"),
    ("PO-113", "edta", 5, 50, "plan", "Draft"),         # covers that shortage a week later
    # after the eight weeks
    ("PO-116", "cetyl", 50, 64, "plan", "Confirmed"),
    # history
    ("PO-095", "pq7", 20, -12, "plan", "Received"),
    ("PO-096", "3005", 300, -7, "plan", "Received"),
    ("PO-123", "jojoba", 25, 24, "plan", "Cancelled"),
]


def _name(he: str, en: str) -> str:
    return f"{he} / {en}"


def _nice(value: float) -> float:
    """Round up to a tidy quantity."""
    if value <= 0:
        return 0
    step = 10 ** max(0, int(math.log10(value)) - 1)
    return math.ceil(value / step) * step


def load_sample_formulas(conn: sqlite3.Connection, today: date | None = None) -> None:
    """Replace the catalog, trees, plan, orders and records with the sample data.

    Everything happens in one transaction. The eight-week plan starts in the current week.
    """
    init_db(conn)  # creates the tables when the database is new
    today = today or date.today()
    start = current_plan_start(today)
    now = today.isoformat()

    def day(offset: int) -> str:
        return (today + timedelta(days=offset)).isoformat()

    with conn:
        c = conn.cursor()
        c.execute("DELETE FROM Batches WHERE sku NOT IN (SELECT sku FROM Catalog WHERE primary_warehouse = 'WH_COLOR')")
        c.execute("DELETE FROM Catalog WHERE primary_warehouse IS NOT 'WH_COLOR'")
        for table in ("BOM", "WeeklySchedule", "PurchaseOrders", "StockMovements", "BatchConsumption",
                      "TableBackups", "Projects", "AltSkus", "Shipments"):
            c.execute(f"DELETE FROM {table}")

        def item(sku, label, kind, units, grams, supplier, price, moq, warehouse, shelf_days):
            c.execute("INSERT INTO Catalog VALUES (?,?,?,?,?,'0','-',?,'-','-',?,?,?,?,?)",
                      (sku, label, kind, units, grams, supplier, price, moq, price, warehouse, f"SAP-{sku}"))
            if units or grams:
                expiry = (today + timedelta(days=shelf_days)).isoformat() if shelf_days else ""
                c.execute("INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, "
                          "source, status) VALUES (?,?,?,?,?,?,'OPENING','Active')",
                          (sku, f"OPEN-{sku}", units, grams, expiry, now))

        # Raw materials: enough for the eight-week plan plus a margin, except the deliberately short ones.
        need_kg = {key: sum(f.get(key, 0) * sum(plan) / 1000 for *_, plan, f in BULK.values()) for key in RAW}
        for key, (he, en, price, supplier, moq) in RAW.items():
            stock = RAW_STOCK_KG.get(key, _nice(max(need_kg[key] * 1.3, moq)))
            item(RAW_SKU[key], _name(he, en), "RAW", 0, stock * 1000, supplier, price, moq, "WH_RAW",
                 None if key == "aqua" else 365)

        for sku, (he, en, stock_kg, plan, formula) in BULK.items():
            cost = round(sum(qty * RAW[key][2] for key, qty in formula.items()) / 1000, 2)
            item(sku, _name(f"בלק {he}", f"{en} bulk"), "BULK", 0, stock_kg * 1000, "קו ייצור פנימי", cost, 100,
                 "WH_BULK", 180)
            for key, qty in formula.items():
                c.execute("INSERT INTO BOM VALUES (?,?,'RAW',0,?)", (sku, RAW_SKU[key], qty))
            c.execute("INSERT INTO WeeklySchedule VALUES (?,?,?,?,?,?,?,?,?)", (sku, *plan))

        pack_need = {sku: sum(sum(f[4]) for f in FG.values() if sku in f[7]) for sku in PKG}
        for sku, (he, en, price, supplier) in PKG.items():
            item(sku, _name(he, en), "PKG", PKG_STOCK.get(sku, _nice(pack_need[sku] * 1.2)), 0,
                 supplier, price, 500, "WH_PACK", None)

        for sku, (he, en, price, stock, plan, bulk, grams, packaging) in FG.items():
            item(sku, _name(he, en), "FG", stock, 0, "מחלקת אריזה", price, 50, "WH_FG", 730)
            c.execute("INSERT INTO BOM VALUES (?,?,'BULK',0,?)", (sku, bulk, grams))
            for part in packaging:
                c.execute("INSERT INTO BOM VALUES (?,?,'PKG',1,0)", (sku, part))
            c.execute("INSERT INTO WeeklySchedule VALUES (?,?,?,?,?,?,?,?,?)", (sku, *plan))

        on_the_way: dict[str, list[tuple[date, str]]] = {}
        for number, key, qty, days, counted_from, status in ORDERS:
            sku = RAW_SKU.get(key, key)
            is_raw = key in RAW
            eta = (today if counted_from == "today" else start) + timedelta(days=days)
            supplier, price = (RAW[key][3], RAW[key][2]) if is_raw else (PKG[key][3], PKG[key][2])
            c.execute("INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, "
                      "unit_price, order_date, eta_date, target_wh, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (number, sku, supplier, 0 if is_raw else qty, qty * 1000 if is_raw else 0, price,
                       min(today, eta - timedelta(days=14)).isoformat(), eta.isoformat(),
                       "WH_RAW" if is_raw else "WH_PACK", status))
            if status not in ("Received", "Cancelled"):
                amount = f'{qty:g} ק"ג' if is_raw else f"{qty:g} יח'"
                on_the_way.setdefault(sku, []).append((eta, f"{amount} ({number})"))
        for sku, notes in on_the_way.items():
            c.execute("UPDATE Catalog SET open_orders = ? WHERE sku = ?",
                      (", ".join(note for _, note in sorted(notes)), sku))

        c.executemany("INSERT INTO Projects (code, name, customer, sku, status, start_date, due_date) VALUES (?,?,?,?,?,?,?)", [
            ("DEMO-001", "השקת שמפו היאלורוני (דוגמה)", "לקוח דמו א", "5002", "Active", day(-30), day(45)),
            ("DEMO-002", "מסכת שיער בגודל 1 ליטר (דוגמה)", "לקוח דמו ב", "5005", "Active", day(-10), day(90)),
            ("DEMO-003", "מארז ווקס לחג (דוגמה)", "לקוח דמו א", "5001", "On hold", day(-60), day(20)),
            ("DEMO-004", "אריזה מחודשת לקרם ידיים (דוגמה)", "לקוח דמו ג", "5006", "Done", day(-120), day(-30)),
        ])
        for key, text in ALTERNATIVES:
            sku = RAW_SKU.get(key, key)
            c.execute("INSERT INTO AltSkus (sku, alt_sku, description, priority) VALUES (?,?,?,1)", (sku, f"{sku}-B", text))
        c.executemany("INSERT INTO Shipments (shipment_no, customer, carrier, ship_type, sku, qty_units, ship_date, status) "
                      "VALUES (?,?,?,?,?,?,?,?)", [
            ("SH-1001", "לקוח דמו א", "חברת שליחים (דוגמה)", "שליח", "5002", 120, day(-3), "Delivered"),
            ("SH-1002", "לקוח דמו ב", "הובלה אווירית (דוגמה)", "אווירי", "5004", 300, day(1), "In transit"),
            ("SH-1003", "לקוח דמו ג", "הובלה ימית (דוגמה)", "ימי", "5006", 2400, day(14), "Planned"),
        ])
        c.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES (?, ?)", (PLAN_START_KEY, start.isoformat()))
        # Stops the app's own starting rows from ever being loaded on top of this data.
        c.execute("INSERT OR REPLACE INTO Settings (key, value) VALUES ('demo_reset_done', '1')")
        c.execute("INSERT INTO AuditLog (at, scope, action) VALUES (?, 'catalog', ?)",
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   "נטענו נתוני הדוגמה / Sample data loaded"))
