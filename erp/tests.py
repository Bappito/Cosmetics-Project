import shutil
import tempfile
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase


class _DashboardTestSetup:
    def setUp(self):
        # Give the tests their own copy of the ERP database so they never touch the real one.
        self.tmp = Path(tempfile.mkdtemp())
        self.erp_db = self.tmp / "erp.db"
        self.enterContext(self.settings(ERP_DB_PATH=str(self.erp_db)))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.client = Client()

    def make_user(self, username, group=None):
        user = User.objects.create_user(username=username, password="pw-test-123")
        if group:
            user.groups.add(Group.objects.get(name=group))
        return user

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/login/?next=/")

    def test_user_without_dashboard_permission_is_refused(self):
        self.make_user("nobody")
        self.client.login(username="nobody", password="pw-test-123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 403)

    def test_viewer_group_sees_dashboard(self):
        self.make_user("viewer", group="Viewer")
        self.client.login(username="viewer", password="pw-test-123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "לוח בקרה")  # Hebrew title by default
        self.assertContains(response, 'dir="rtl"')

    def test_english_toggle_switches_direction(self):
        self.make_user("viewer", group="Viewer")
        self.client.login(username="viewer", password="pw-test-123")
        self.client.post("/settings/language/en/")
        response = self.client.get("/")
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, "Open purchase orders")

    def test_sidebar_hides_screens_the_user_cannot_view(self):
        self.make_user("viewer", group="Viewer")
        self.client.login(username="viewer", password="pw-test-123")
        response = self.client.get("/")
        # The viewer only has the dashboard, so no other screen is listed in the sidebar.
        self.assertEqual(len(response.context["nav"]), 1)

    def test_admin_group_sees_every_screen_in_sidebar(self):
        self.make_user("admin", group="Admin")
        self.client.login(username="admin", password="pw-test-123")
        response = self.client.get("/")
        self.assertEqual(len(response.context["nav"]), 16)

    def test_default_groups_exist_after_migration(self):
        self.assertTrue(Group.objects.filter(name="Admin").exists())
        self.assertTrue(Group.objects.filter(name="Viewer").exists())


class DashboardAccessTests(_DashboardTestSetup, TestCase):
    pass


class ProfitAndRoleTests(_DashboardTestSetup, TestCase):
    """Profit is visible only with the view_profit permission; the Warehouse role exists."""

    def test_viewer_does_not_see_profit(self):
        self.make_user("viewer", group="Viewer")
        self.client.login(username="viewer", password="pw-test-123")
        response = self.client.post("/settings/language/en/")
        response = self.client.get("/")
        self.assertNotContains(response, "Estimated profit per finished product")

    def test_admin_sees_profit(self):
        self.make_user("boss", group="Admin")
        self.client.login(username="boss", password="pw-test-123")
        self.client.post("/settings/language/en/")
        response = self.client.get("/")
        self.assertContains(response, "Estimated profit per finished product")

    def test_warehouse_group_has_warehouse_screens_but_no_profit(self):
        from django.contrib.auth.models import Group
        group = Group.objects.get(name="Warehouse")
        codenames = set(group.permissions.values_list("codename", flat=True))
        self.assertIn("view_inventory", codenames)
        self.assertIn("edit_purchase_orders", codenames)
        self.assertNotIn("view_profit", codenames)

    def test_wrong_password_is_refused(self):
        self.make_user("viewer", group="Viewer")
        response = self.client.post("/login/", {"username": "viewer", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)


# ---------------------------------------------------------------------------
# Screens: every page renders, permissions gate them, and the write flows work.
# ---------------------------------------------------------------------------

import csv
import io
import json
from datetime import date, timedelta

from django.test import override_settings
from django.urls import reverse


class ScreenTestBase(TestCase):
    """Gives each test a fresh ERP database (demo data is created on first use) and a logged-in user."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.override = override_settings(ERP_DB_PATH=str(self.tmp / "erp.db"))
        self.override.enable()
        self.addCleanup(self.override.disable)
        from erp.bridge import open_erp_connection
        open_erp_connection().close()  # creates the schema and demo data in the temp database
        self.client = Client()
        self.user = User.objects.create_user(username="admin", password="pw-test-123")
        self.user.groups.add(Group.objects.get(name="Admin"))
        self.client.login(username="admin", password="pw-test-123")

    def erp(self):
        """The ERP database the app is using, opened directly for assertions."""
        import sqlite3
        return sqlite3.connect(self.tmp / "erp.db")

    def query(self, sql, *args):
        conn = self.erp()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()

    def first_sku(self, item_type):
        return self.query("SELECT sku FROM Catalog WHERE item_type = ? ORDER BY sku", item_type)[0][0]


class ScreensRenderTests(ScreenTestBase):
    PAGES = [
        "/", "/inventory/", "/inventory/?tab=po", "/inventory/?tab=sup", "/inventory/?tab=edit",
        "/inventory/?tab=count", "/inventory/?tab=import&wh=BULK", "/inventory/?wh=PKG", "/inventory/?wh=FG",
        "/po-list/", "/stock-summary/", "/projects/", "/alt-skus/", "/prr/?kind=packaging", "/prr/export/?kind=packaging&only=short", "/shipments/", "/scenarios/", "/production-planning/?view=packaging", "/purchase-orders/", "/mrp/", "/mrp/export/", "/batches/", "/batches/?tab=receipt",
        "/batches/?tab=trace", "/bom/", "/bom/tree/2001/", "/bom/?mode=new", "/production/", "/packaging/?view=bulk",
        "/packaging/?view=pkg", "/master-work/", "/quick-command/", "/audit/",
    ]

    def test_every_screen_renders_for_admin(self):
        for url in self.PAGES:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200, url)

    def test_hebrew_default_and_english_toggle(self):
        response = self.client.get("/inventory/")
        self.assertContains(response, 'dir="rtl"')
        self.client.post("/settings/language/en/")
        response = self.client.get("/inventory/")
        self.assertContains(response, 'dir="ltr"')
        self.assertContains(response, "Warehouses (stock, expiry &amp; PO)")

    def test_weight_unit_switch_changes_labels(self):
        self.client.post("/settings/language/en/")
        self.client.post("/settings/unit/g/")
        response = self.client.get("/inventory/?wh=RAW")
        self.assertContains(response, "(g)")

    def test_dark_theme_switch(self):
        self.client.post("/settings/theme/dark/")
        response = self.client.get("/")
        self.assertContains(response, 'data-theme="dark"')

    def test_external_next_is_not_followed(self):
        response = self.client.post("/settings/language/en/", {"next": "https://evil.example/"})
        self.assertRedirects(response, "/", fetch_redirect_response=False)


class PermissionTests(ScreenTestBase):
    def test_viewer_is_refused_on_warehouse_screen(self):
        Viewer = User.objects.create_user(username="viewer", password="pw-test-123")
        Viewer.groups.add(Group.objects.get(name="Viewer"))
        self.client.login(username="viewer", password="pw-test-123")
        self.assertEqual(self.client.get("/inventory/").status_code, 403)
        self.assertEqual(self.client.get("/audit/").status_code, 403)
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_warehouse_cannot_post_to_mrp(self):
        Wh = User.objects.create_user(username="wh", password="pw-test-123")
        Wh.groups.add(Group.objects.get(name="Warehouse"))
        self.client.login(username="wh", password="pw-test-123")
        response = self.client.post("/mrp/", {"action": "create", "confirmed": "1"})
        self.assertEqual(response.status_code, 403)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get("/inventory/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])


class PurchaseOrderListTests(ScreenTestBase):
    def test_list_shows_every_order_and_filters_by_search(self):
        response = self.client.get("/po-list/")
        self.assertEqual(response.status_code, 200)
        total = self.query("SELECT COUNT(*) FROM PurchaseOrders")[0][0]
        self.assertContains(response, f"Order list ({total})".replace("Order list", "רשימת הזמנות"))
        po = self.query("SELECT po_number FROM PurchaseOrders ORDER BY po_id LIMIT 1")[0][0]
        response = self.client.get("/po-list/", {"q": po})
        self.assertContains(response, po)

    def test_viewer_with_list_permission_can_open_list_but_not_management(self):
        from django.contrib.auth.models import Permission
        Reader = User.objects.create_user(username="reader", password="pw-test-123")
        Reader.user_permissions.add(Permission.objects.get(codename="view_po_list"))
        self.client.login(username="reader", password="pw-test-123")
        self.assertEqual(self.client.get("/po-list/").status_code, 200)
        self.assertEqual(self.client.get("/purchase-orders/").status_code, 403)


class QuickCommandTests(ScreenTestBase):
    def test_command_is_reviewed_then_applied(self):
        sku = self.first_sku("FG")
        before = self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0]
        self.client.post("/quick-command/", {"action": "submit", "command": f"add 5 units to {sku}"})
        self.assertEqual(self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0], before)  # not yet
        self.client.post("/quick-command/", {"action": "confirm", "confirmed": "1"})
        self.assertEqual(self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0], before + 5)

    def test_wrong_unit_is_refused(self):
        sku = self.first_sku("RAW")
        self.client.post("/quick-command/", {"action": "submit", "command": f"add 5 units to {sku}"})
        self.assertIsNone(self.client.session.get("pending:quick_command"))

    def test_undo_restores_stock(self):
        sku = self.first_sku("FG")
        before = self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0]
        self.client.post("/quick-command/", {"action": "submit", "command": f"add 7 units to {sku}"})
        self.client.post("/quick-command/", {"action": "confirm", "confirmed": "1"})
        self.client.post("/undo/quick_command/stock/", {"next": "/quick-command/"})
        self.assertEqual(self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0], before)


class PurchaseOrderTests(ScreenTestBase):
    def test_receive_order_creates_batch_and_marks_received(self):
        po = self.query("SELECT po_number, sku FROM PurchaseOrders WHERE status NOT IN ('Received','Cancelled') ORDER BY po_id LIMIT 1")
        if not po:
            self.skipTest("demo data has no open purchase order")
        po_number, sku = po[0]
        self.client.get(f"/purchase-orders/?po={po_number}")
        self.client.post("/purchase-orders/", {
            "action": "receipt_review", "po_number": po_number, "batch": f"TEST-{sku}",
            "expiry": (date.today() + timedelta(days=200)).isoformat(),
        })
        self.client.post("/purchase-orders/", {"action": "receipt_confirm", "confirmed": "1"})
        status = self.query("SELECT status FROM PurchaseOrders WHERE po_number=?", po_number)[0][0]
        self.assertEqual(status, "Received")
        self.assertEqual(self.query("SELECT COUNT(*) FROM Batches WHERE sku=? AND batch_no=?", sku, f"TEST-{sku}")[0][0], 1)

    def test_po_edit_requires_review_before_save(self):
        response = self.client.get("/purchase-orders/")
        rows = response.context["editable"]
        self.assertTrue(rows)
        po_number = rows[0]["po_number"]
        data = {"action": "po_review", "row_count": str(len(rows))}
        for i, r in enumerate(rows):
            data[f"po_id_{i}"] = str(r.get("po_id", ""))
            for f in ("po_number", "sku", "supplier", "order_qty_units", "order_weight_grams", "unit_price", "order_date", "eta_date", "target_wh", "status"):
                data[f"{f}_{i}"] = str(r.get(f, ""))
        data["supplier_0"] = "Changed Supplier"
        self.client.post("/purchase-orders/", data)
        self.assertEqual(self.query("SELECT supplier FROM PurchaseOrders WHERE po_number=?", po_number)[0][0] != "Changed Supplier", True)
        self.assertIsNotNone(self.client.session.get("pending:po"))
        self.client.post("/purchase-orders/", {"action": "po_confirm", "confirmed": "1"})
        self.assertEqual(self.query("SELECT supplier FROM PurchaseOrders WHERE po_number=?", po_number)[0][0], "Changed Supplier")


class MrpTests(ScreenTestBase):
    def test_mrp_creates_monthly_draft_orders(self):
        response = self.client.get("/mrp/")
        if not response.context["has_suggestions"]:
            self.skipTest("demo plan needs nothing to buy")
        self.client.post("/mrp/", {"action": "create", "confirmed": "1"})
        drafts = self.query("SELECT po_number, sku, eta_date FROM PurchaseOrders WHERE status = 'Draft'")
        self.assertTrue(drafts)
        self.assertTrue(all(po.startswith("MRP-") for po, _, _ in drafts))
        pairs = [(sku, eta[:7]) for _, sku, eta in drafts]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_mrp_excel_download(self):
        response = self.client.get("/mrp/export/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("spreadsheetml", response["Content-Type"])


class ScheduleAndRunTests(ScreenTestBase):
    def test_quick_planner_sets_week_and_can_be_undone(self):
        sku = self.first_sku("FG")
        self.client.post("/production/", {"action": "plan"})  # no-op submit with missing values is refused
        self.client.post("/master-work/", {"action": "plan", "plan_sku": sku, "plan_week": "W3", "plan_qty": "42"})
        self.assertEqual(self.query(f"SELECT W3 FROM WeeklySchedule WHERE parent_sku=?", sku)[0][0], 42)
        self.client.post(f"/undo/master_work/schedule/", {"next": "/master-work/"})
        self.assertNotEqual(self.query(f"SELECT W3 FROM WeeklySchedule WHERE parent_sku=?", sku)[0][0], 42)

    def test_production_run_posts_and_creates_bulk_batch(self):
        bulk = self.first_sku("BULK")
        self.client.get("/production/")
        response = self.client.post("/production/", {
            "action": "run", "bulk_sku": bulk, "kg": "1", "batch": "RUN-TEST-1",
            "expiry": (date.today() + timedelta(days=180)).isoformat(),
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        count = self.query("SELECT COUNT(*) FROM Batches WHERE sku=? AND batch_no='RUN-TEST-1'", bulk)[0][0]
        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(count == 1 or any("short" in m or "חסרים" in m or "Cannot" in m or "לא ניתן" in m for m in messages))

    def test_packaging_run_with_zero_units_is_refused(self):
        self.client.post("/settings/language/en/")
        fg = self.first_sku("FG")
        response = self.client.post("/packaging/", {"action": "run", "fg_sku": fg, "units": "0", "expiry": date.today().isoformat()}, follow=True)
        self.assertContains(response, "at least one unit")


class CatalogAndCountTests(ScreenTestBase):
    def test_catalog_editor_review_then_confirm(self):
        response = self.client.get("/inventory/?tab=edit")
        rows = response.context["catalog_editable"]
        data = {"action": "review", "row_count": str(len(rows))}
        for i, r in enumerate(rows):
            for f in ("sku", "name", "item_type", "stock_val", "open_orders", "stock_movements", "main_supplier", "alt_suppliers", "last_stock_entry"):
                data[f"{f}_{i}"] = str(r.get(f, "") or "")
        data["name_0"] = data["name_0"] + " (edited)"
        self.client.post("/inventory/?tab=edit", data)
        self.assertIsNotNone(self.client.session.get("pending:catalog"))
        self.client.post("/inventory/?tab=edit", {"action": "confirm", "confirmed": "1"})
        names = self.query("SELECT name FROM Catalog WHERE sku=?", rows[0]["sku"])
        self.assertTrue(names[0][0].endswith("(edited)"))

    def test_count_difference_is_applied_after_confirmation(self):
        sku = self.first_sku("PKG")
        response = self.client.get("/inventory/?tab=count&wh=PKG")
        rows = response.context["count_rows"]
        index = next(i for i, r in enumerate(rows) if r["sku"] == sku)
        # The form posts every counted field; unchanged rows keep the system value.
        data = {"action": "review"}
        for i, r in enumerate(rows):
            data[f"counted_{i}"] = "999" if i == index else str(r["system"])
        self.client.post("/inventory/?tab=count&wh=PKG", data)
        self.assertIsNotNone(self.client.session.get("pending:count"))
        self.client.post("/inventory/?tab=count&wh=PKG", {"action": "confirm", "confirmed": "1"})
        self.assertEqual(self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0], 999)


class ErpImportTests(ScreenTestBase):
    def _csv(self, rows):
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["MATNR", "LABST"])
        writer.writerows(rows)
        return io.BytesIO(out.getvalue().encode("utf-8"))

    def test_stock_import_upload_map_confirm(self):
        sku = self.first_sku("PKG")
        upload = self._csv([[sku, "250"]])
        upload.name = "stock.csv"
        self.client.post("/inventory/?tab=import&wh=PKG", {"action": "upload", "file": upload})
        self.assertIsNotNone(self.client.session.get("pending:import_file"))
        self.client.post("/inventory/?tab=import&wh=PKG", {
            "action": "map", "kind": "stock", "unit": "kg", "map_sku": "MATNR", "map_qty": "LABST",
        })
        self.assertIsNotNone(self.client.session.get("pending:import"))
        self.client.post("/inventory/?tab=import&wh=PKG", {"action": "confirm", "confirmed": "1"})
        self.assertEqual(self.query("SELECT qty_units FROM Catalog WHERE sku=?", sku)[0][0], 250)


class BomTests(ScreenTestBase):
    def test_new_bulk_tree_is_saved(self):
        raw = self.first_sku("RAW")
        response = self.client.post("/bom/", {
            "mode": "new", "new_sku": "NEW-BULK-1", "new_name": "Test bulk", "new_type": "BULK",
            "row_count": "1", "comp_0": raw, "qty_0": "250", "confirmed": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.query("SELECT COUNT(*) FROM BOM WHERE parent_sku='NEW-BULK-1'")[0][0], 1)

    def test_tree_with_wrong_component_type_is_refused(self):
        raw = self.first_sku("RAW")
        response = self.client.post("/bom/", {
            "mode": "new", "new_sku": "NEW-FG-BAD", "new_name": "Bad", "new_type": "FG",
            "row_count": "1", "comp_0": raw, "qty_0": "5", "confirmed": "1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.query("SELECT COUNT(*) FROM Catalog WHERE sku='NEW-FG-BAD'")[0][0], 0)


class AuditTests(ScreenTestBase):
    def test_undo_is_logged_and_listed(self):
        sku = self.first_sku("FG")
        self.client.post("/quick-command/", {"action": "submit", "command": f"add 2 units to {sku}"})
        self.client.post("/quick-command/", {"action": "confirm", "confirmed": "1"})
        self.client.post("/undo/quick_command/stock/", {"next": "/quick-command/"})
        response = self.client.get("/audit/")
        actions = [e["action"] for e in response.context["entries"]]
        self.assertTrue(any(a.startswith("UNDO") for a in actions))


class PrrAndSummaryTests(ScreenTestBase):
    def test_prr_colours_follow_the_stock_rule(self):
        response = self.client.get("/prr/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["rows"])
        statuses = {c["status"] for r in response.context["rows"] for c in r["weeks"]}
        self.assertTrue(statuses <= {"green", "yellow", "red", "none"})
        self.assertContains(response, "prr-")

    def test_prr_export_is_csv_with_one_line_per_week(self):
        response = self.client.get("/prr/export/?kind=production")
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        lines = response.content.decode("utf-8").strip().splitlines()
        self.assertEqual(lines[0].split(",")[0], "SKU")
        self.assertGreaterEqual(len(lines), 2)

    def test_warehouse_screen_shows_summary_cards(self):
        self.client.post("/settings/language/en/")
        response = self.client.get("/inventory/")
        labels = [m["label"] for m in response.context["summary"]]
        self.assertIn("Unique SKUs", labels)

    def test_viewer_cannot_open_prr(self):
        viewer = User.objects.create_user(username="v2", password="pw-test-123")
        viewer.groups.add(Group.objects.get(name="Viewer"))
        self.client.login(username="v2", password="pw-test-123")
        self.assertEqual(self.client.get("/prr/").status_code, 403)


class ScenarioPrivacyTests(ScreenTestBase):
    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User as AuthUser
        from erp.models import Scenario
        self.Scenario = Scenario
        self.other = AuthUser.objects.create_user(username="other", password="pw-test-123")
        self.other.groups.add(Group.objects.get(name="Warehouse"))

    def test_owner_creates_and_saves_a_scenario(self):
        self.client.post("/scenarios/", {"action": "create", "name": "Plan A"})
        scenario = self.Scenario.objects.get(name="Plan A")
        self.client.post("/scenarios/", {
            "action": "save", "scenario_id": scenario.pk, "row_count": "1",
            "line_sku_0": "5001", "line_week_0": "2", "line_qty_0": "100",
        })
        scenario.refresh_from_db()
        self.assertEqual(scenario.lines, [{"sku": "5001", "week": 2, "qty": 100.0}])

    def test_private_scenario_is_hidden_from_other_users(self):
        scenario = self.Scenario.objects.create(owner=self.user, name="Secret", lines=[])
        self.client.login(username="other", password="pw-test-123")
        self.assertEqual(self.client.get(f"/scenarios/?id={scenario.pk}").status_code, 404)

    def test_shared_scenario_is_visible_but_not_editable_by_others(self):
        scenario = self.Scenario.objects.create(owner=self.user, name="Shared", lines=[], shared=True)
        self.client.login(username="other", password="pw-test-123")
        self.assertEqual(self.client.get(f"/scenarios/?id={scenario.pk}").status_code, 200)
        self.client.post("/scenarios/", {"action": "delete", "scenario_id": scenario.pk})
        self.assertTrue(self.Scenario.objects.filter(pk=scenario.pk).exists())


class MenuOrderTests(ScreenTestBase):
    def test_admin_moves_a_menu_item_up(self):
        from erp.layout import saved_menu_order
        before = [i['key'] for i in self.client.get('/').context['nav']]
        target = before[2]
        expected = list(before)
        idx = expected.index(target)
        expected[idx - 1], expected[idx] = expected[idx], expected[idx - 1]
        self.client.post('/menu-order/', {'action': 'up', 'key': target})
        after = [i['key'] for i in self.client.get('/').context['nav']]
        self.assertEqual(after, expected)
        self.assertEqual(saved_menu_order(), expected)

    def test_reset_returns_default_order(self):
        self.client.post('/menu-order/', {'action': 'up', 'key': 'purchase_orders'})
        self.client.post('/menu-order/', {'action': 'reset'})
        from erp.layout import saved_menu_order
        self.assertEqual(saved_menu_order(), [])

    def test_non_admin_cannot_change_the_menu(self):
        Viewer = User.objects.create_user(username='viewer2', password='pw-test-123')
        Viewer.groups.add(Group.objects.get(name='Viewer'))
        self.client.login(username='viewer2', password='pw-test-123')
        self.assertEqual(self.client.get('/menu-order/').status_code, 403)


class OneLanguageNameTests(ScreenTestBase):
    def test_bom_tree_shows_only_the_page_language(self):
        self.client.post("/settings/language/en/")
        english = self.client.get("/bom/tree/5001/").content.decode("utf-8")
        self.assertIn("Cream Base", english)
        self.assertNotIn("בסיס אמולסיה לקרם", english)
        self.client.post("/settings/language/he/")
        hebrew = self.client.get("/bom/tree/5001/").content.decode("utf-8")
        self.assertIn("בסיס אמולסיה לקרם", hebrew)
        self.assertNotIn("Cream Base", hebrew)
