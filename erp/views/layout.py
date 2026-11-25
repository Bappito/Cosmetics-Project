"""Admin page to change the order of the sidebar menu."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods

from erp.layout import save_menu_order, saved_menu_order

from .page import Page, nav_items


@login_required
@require_http_methods(["GET", "POST"])
def menu_order(request):
    if not request.user.has_perm("erp.edit_dashboard"):  # Admin group (and superusers) only
        raise PermissionDenied
    with Page(request, "dashboard") as page:
        current = nav_items(request.user, "", page.lang)
        keys = [item["key"] for item in current]

        if request.method == "POST":
            action = request.POST.get("action", "")
            key = request.POST.get("key", "")
            if action == "reset":
                save_menu_order([])
            elif action in ("up", "down") and key in keys:
                i = keys.index(key)
                j = i - 1 if action == "up" else i + 1
                if 0 <= j < len(keys):
                    keys[i], keys[j] = keys[j], keys[i]
                    save_menu_order(keys)
            return redirect("menu_order")

        labels = {item["key"]: item["label"] for item in current}
        rows = [{"key": k, "label": labels[k], "first": i == 0, "last": i == len(keys) - 1}
                for i, k in enumerate(keys)]
        return page.render(
            "erp/menu_order.html",
            title=page.L("סדר התפריט", "Menu order"),
            subtitle=page.L("שנה את סדר הפריטים בתפריט הצד. השינוי נשמר לכל המשתמשים.",
                            "Change the order of the sidebar items. The change applies to all users."),
            rows=rows,
            has_saved=bool(saved_menu_order()),
        )
