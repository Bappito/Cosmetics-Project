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
        self.client.get("/language/en/")
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
        self.assertEqual(len(response.context["nav"]), 9)

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
        response = self.client.get("/language/en/")
        response = self.client.get("/")
        self.assertNotContains(response, "Estimated profit per finished product")

    def test_admin_sees_profit(self):
        self.make_user("boss", group="Admin")
        self.client.login(username="boss", password="pw-test-123")
        self.client.get("/language/en/")
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
