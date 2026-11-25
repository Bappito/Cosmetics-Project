from django.conf import settings
from django.db import models

from .screens import permission_choices


class ScreenAccess(models.Model):
    """Holds the per-screen permissions. It has no table of its own.

    The ERP data itself is in the existing SQLite file and is read through erp/bridge.py,
    so this model is unmanaged: it exists only to attach permissions to.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = permission_choices()
        verbose_name = "screen access"
        verbose_name_plural = "screen access"


class Scenario(models.Model):
    """A personal what-if plan: planned finished-product orders by week.

    Private to its owner unless shared. Shared scenarios are read-only for everyone else.
    """

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scenarios")
    name = models.CharField(max_length=120)
    lines = models.JSONField(default=list, blank=True)
    shared = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.name


class LayoutSetting(models.Model):
    """Small layout settings the admin can change, such as the order of the sidebar menu."""

    key = models.CharField(max_length=60, unique=True)
    value = models.JSONField(default=list, blank=True)

    def __str__(self) -> str:
        return self.key
