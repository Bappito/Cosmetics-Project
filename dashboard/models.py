from django.db import models


class ScreenAccess(models.Model):
    """Holds the screen permissions. It has no table of its own; Django only needs the permission rows."""

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_dashboard", "Can open the dashboard"),
            ("view_profit", "Can see profit per product"),
            ("view_warehouse", "Can view the warehouses"),
            ("edit_warehouse", "Can change stock in the warehouses"),
            ("manage_users", "Can manage users and roles"),
        ]
