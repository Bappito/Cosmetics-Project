from django.apps import AppConfig
from django.db.models.signals import post_migrate

from .screens import ALL_PERMISSIONS, VIEWER_PERMISSIONS


class ErpConfig(AppConfig):
    name = "erp"
    verbose_name = "Cosmetics ERP"

    def ready(self) -> None:
        post_migrate.connect(create_default_groups, sender=self)


def create_default_groups(sender, using="default", apps=None, **kwargs) -> None:
    """Create the starting roles the first time migrations run.

    Groups are created only when missing, so changes an admin makes later in the Django admin
    are never overwritten by a later migration.
    """
    from django.contrib.auth.management import create_permissions
    from django.contrib.auth.models import Group, Permission

    # The screen permissions belong to an unmanaged model, so create them explicitly before use.
    create_permissions(sender, verbosity=0, using=using, apps=apps)

    def perms(codenames):
        return Permission.objects.using(using).filter(content_type__app_label="erp", codename__in=codenames)

    admin_group, created = Group.objects.using(using).get_or_create(name="Admin")
    if created:
        admin_group.permissions.set(perms(ALL_PERMISSIONS))

    viewer_group, created = Group.objects.using(using).get_or_create(name="Viewer")
    if created:
        viewer_group.permissions.set(perms(VIEWER_PERMISSIONS))
