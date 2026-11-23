"""The screens of the ERP and the permissions that control them.

Every screen has two permissions:
- ``view_<screen>``: the user can open the screen and see its data.
- ``edit_<screen>``: the user can enter or change data on it.

Admins assign these to groups in the Django admin (Authentication and authorization > Groups).
"""

# key -> (Hebrew label, English label, is the screen ported to the web app yet?)
SCREENS = {
    "dashboard": ("לוח בקרה", "Dashboard", True),
    "inventory": ("מלאי ומחסנים", "Inventory & warehouses", False),
    "purchase_orders": ("הזמנות רכש", "Purchase orders", False),
    "mrp": ("תכנון שמונה שבועות", "Eight-week planning", False),
    "batches": ("אצוות ומעקב", "Batches & tracing", False),
    "production": ("סימולציית ייצור", "Production simulation", False),
    "packaging": ("סימולציית אריזה", "Packaging simulation", False),
    "master_work": ("עבודה מול המאסטר", "Master data", False),
    "quick_command": ("פקודה מהירה", "Quick command", False),
}

ALL_PERMISSIONS = [
    f"{action}_{key}" for key in SCREENS for action in ("view", "edit")
]

# What a read-only user gets by default. Only the dashboard for now.
VIEWER_PERMISSIONS = ["view_dashboard"]


def permission_choices():
    """(codename, label) pairs for the ScreenAccess model Meta.permissions."""
    choices = []
    for key, (_he, en, _ported) in SCREENS.items():
        choices.append((f"view_{key}", f"Can view {en}"))
        choices.append((f"edit_{key}", f"Can edit {en}"))
    return choices
