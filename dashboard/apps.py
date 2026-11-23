from django.apps import AppConfig
from django.db.models.signals import post_migrate

ROLES = {
    "Admin": [
        "view_dashboard", "view_profit", "view_warehouse", "edit_warehouse", "manage_users",
    ],
    "Warehouse": ["view_dashboard", "view_warehouse", "edit_warehouse"],
    "Viewer": ["view_dashboard"],
}


def create_roles(sender, **kwargs):
    """Create the standard roles after permissions exist. Re-running keeps them in sync."""
    from django.contrib.auth.models import Group, Permission

    for name, codenames in ROLES.items():
        group, _ = Group.objects.get_or_create(name=name)
        perms = Permission.objects.filter(content_type__app_label="dashboard", codename__in=codenames)
        group.permissions.set(perms)


class DashboardConfig(AppConfig):
    name = "dashboard"

    def ready(self):
        post_migrate.connect(create_roles, sender=self)
