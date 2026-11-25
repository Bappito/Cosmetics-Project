from django.urls import path

from .views import batches, dashboard, inventory, layout, operations, planning, purchasing, readiness, records, scenarios, stock

urlpatterns = [
    path("", dashboard.dashboard, name="dashboard"),
    path("inventory/", inventory.inventory, name="inventory"),
    path("po-list/", purchasing.po_list, name="po_list"),
    path("stock-summary/", stock.stock_summary, name="stock_summary"),
    path("projects/", records.projects, name="projects"),
    path("alt-skus/", records.alt_skus, name="alt_skus"),
    path("shipments/", records.shipments, name="shipments"),
    path("scenarios/", scenarios.scenarios, name="scenarios"),
    path("purchase-orders/", purchasing.purchase_orders, name="purchase_orders"),
    path("mrp/", purchasing.mrp, name="mrp"),
    path("mrp/export/", purchasing.mrp_export, name="mrp_export"),
    path("batches/", batches.batches, name="batches"),
    path("bom/", planning.bom, name="bom"),
    path("bom/tree/<str:sku>/", planning.bom_tree, name="bom_tree"),
    path("production-planning/", planning.production_planning, name="production_planning"),
    path("production/", planning.production, name="production"),
    path("packaging/", planning.packaging, name="packaging"),
    path("master-work/", planning.master_work, name="master_work"),
    path("quick-command/", operations.quick_command, name="quick_command"),
    path("menu-order/", layout.menu_order, name="menu_order"),
    path("audit/", operations.audit, name="audit"),
    path("prr/", readiness.prr, name="prr"),
    path("prr/export/", readiness.prr_export, name="prr_export"),
    path("prr-packaging/", readiness.prr_packaging, name="prr_packaging"),
    path("undo/<str:screen>/<str:scope>/", operations.undo, name="undo"),
    path("settings/language/<str:lang>/", operations.set_language, name="set_language"),
    path("settings/unit/<str:unit>/", operations.set_unit, name="set_unit"),
    path("settings/theme/<str:theme>/", operations.set_theme, name="set_theme"),
]
