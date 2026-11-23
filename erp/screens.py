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
    "purchase_orders": ("ניהול הזמנות רכש (PO)", "Purchase orders (PO)"),
    "mrp": ("תכנון רכש (MRP)", "Purchase planning (MRP)"),
    "batches": ("מרשם אצוות ועקיבות (FEFO)", "Batches & traceability (FEFO)"),
    "bom": ("עצי מוצר (BOM)", "Product trees (BOM)"),
    "production": ("1. סימולטור קו ייצור", "1. Production line simulator"),
    "packaging": ("2. סימולטור אריזה", "2. Packaging simulator"),
    "master_work": ("3. סימולטור עבודה מסכם", "3. Master work simulator"),
    "quick_command": ("סוכן פקודות מהיר", "Quick command agent"),
    "audit": ("יומן שינויים", "Change log"),
    "prr": ("PRR — מוכנות פרויקט", "PRR — project readiness"),
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
    "purchase_orders": ("logistics", "cart"),
    "mrp": ("logistics", "calendar"),
    "master_work": ("planning", "clipboard"),
    "production": ("planning", "factory"),
    "packaging": ("planning", "package"),
    "audit": ("ops", "history"),
    "prr": ("planning", "chart"),
}
