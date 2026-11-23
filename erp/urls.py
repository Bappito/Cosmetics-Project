from django.urls import path

from .views import batches, dashboard, inventory, operations, planning, purchasing

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    path("inventory/", inventory.inventory, name="inventory"),
    path("purchase-orders/", purchasing.purchase_orders, name="purchase_orders"),
    path("mrp/", purchasing.mrp, name="mrp"),
    path("mrp/export/", purchasing.mrp_export, name="mrp_export"),
    path("batches/", batches.batches, name="batches"),
    path("bom/", planning.bom, name="bom"),
    path("production/", planning.production, name="production"),
    path("packaging/", planning.packaging, name="packaging"),
    path("master-work/", planning.master_work, name="master_work"),
    path("quick-command/", operations.quick_command, name="quick_command"),
    path("audit/", operations.audit, name="audit"),
    path("undo/<str:screen>/<str:scope>/", operations.undo, name="undo"),
    path("settings/language/<str:lang>/", operations.set_language, name="set_language"),
    path("settings/unit/<str:unit>/", operations.set_unit, name="set_unit"),
    path("settings/theme/<str:theme>/", operations.set_theme, name="set_theme"),
]
