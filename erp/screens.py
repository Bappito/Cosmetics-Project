"""The screens of the ERP and the permissions that control them.

Every screen has two permissions:
- ``view_<screen>``: the user can open the screen and see its data.
- ``edit_<screen>``: the user can enter or change data on it.

Admins assign these to groups in the Django admin (Authentication and authorization > Groups).
"""

# key -> (Hebrew label, English label)
SCREENS = {
    "dashboard": ("לוח בקרה", "Dashboard"),
    "inventory": ("מחסנים (מלאי, תפוגה ורכש)", "Warehouses (stock, expiry & PO)"),
    "po_list": ("הזמנות רכש", "Purchase orders"),
    "stock_summary": ("סיכום מלאי", "Stock summary"),
    "projects": ("פרויקטים", "Projects"),
    "alt_skus": ("מקטים חלופיים", "Alternative SKUs"),
    "shipments": ("משלוחים", "Shipments"),
    "scenarios": ("סימולטור אישי", "My simulator"),
    "purchase_orders": ("ניהול הזמנות רכש (PO)", "Purchase orders management (PO)"),
    "mrp": ("תכנון רכש (MRP)", "Purchase planning (MRP)"),
    "batches": ("מרשם אצוות ועקיבות (FEFO)", "Batches & traceability (FEFO)"),
    "bom": ("עצי מוצר (BOM)", "Product trees (BOM)"),
    "production_planning": ("תכנון ייצור", "Production planning"),
    "production": ("1. סימולטור קו ייצור", "1. Production line simulator"),
    "packaging": ("2. סימולטור אריזה", "2. Packaging simulator"),
    "master_work": ("3. סימולטור עבודה מסכם", "3. Master work simulator"),
    "quick_command": ("סוכן פקודות מהיר", "Quick command agent"),
    "audit": ("יומן שינויים", "Change log"),
    "prr": ("PRR — ייצור", "PRR — production"),
    "prr_packaging": ("PRR — אריזות", "PRR — packaging"),
}

# Permissions that are not a whole screen: the profit section of the dashboard.
EXTRA_PERMISSIONS = [
    ("view_profit", "Can see profit per product"),
]

ALL_PERMISSIONS = [
    f"{action}_{key}" for key in SCREENS for action in ("view", "edit")
] + [codename for codename, _label in EXTRA_PERMISSIONS]

# What a read-only user gets by default. Only the dashboard.
VIEWER_PERMISSIONS = ["view_dashboard"]

# Warehouse staff: the dashboard, the warehouse and purchase-order screens, and editing them.
WAREHOUSE_PERMISSIONS = [
    "view_dashboard",
    "view_inventory", "edit_inventory",
    "view_po_list", "view_stock_summary", "view_shipments", "view_scenarios", "edit_scenarios",
    "view_purchase_orders", "edit_purchase_orders",
]


def permission_choices():
    """(codename, label) pairs for the ScreenAccess model Meta.permissions."""
    choices = []
    for key, (_he, en) in SCREENS.items():
        choices.append((f"view_{key}", f"Can view {en}"))
        choices.append((f"edit_{key}", f"Can edit {en}"))
    return choices + list(EXTRA_PERMISSIONS)


# Sidebar layout: each screen's group (None = the top, ungrouped block) and its icon.
GROUPS = {
    "he": {"ops": "תפעול", "product": "מוצרים", "logistics": "לוגיסטיקה", "planning": "תכנון"},
    "en": {"ops": "Operations", "product": "Products", "logistics": "Logistics", "planning": "Planning"},
}
NAV_LAYOUT = {
    "dashboard": (None, "dashboard"),
    "quick_command": (None, "zap"),
    "bom": ("product", "tree"),
    "inventory": ("logistics", "warehouse"),
    "batches": ("logistics", "qr"),
    "po_list": ("logistics", "cart"),
    "stock_summary": ("logistics", "chart"),
    "projects": ("product", "clipboard"),
    "alt_skus": ("product", "box"),
    "shipments": ("logistics", "truck"),
    "scenarios": ("planning", "play"),
    "purchase_orders": ("logistics", "clipboard"),
    "mrp": ("logistics", "calendar"),
    "master_work": ("planning", "clipboard"),
    "production_planning": ("planning", "factory"),
    "production": ("planning", "factory"),
    "packaging": ("planning", "package"),
    "audit": ("ops", "history"),
    "prr": ("planning", "chart"),
    "prr_packaging": ("planning", "chart"),
}


# The three simulators are shown as tabs on the one production-planning page, not as menu items.
PLANNING_SUBSCREENS = ("production", "packaging", "master_work")
HIDDEN_FROM_NAV = set(PLANNING_SUBSCREENS) | {"prr_packaging"}  # PRR packaging is a tab on the PRR screen
