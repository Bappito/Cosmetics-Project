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
