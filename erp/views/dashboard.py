"""Dashboard: the opening screen with expiry and PO counts, packable units and profit per product."""
from django.contrib.auth.decorators import login_required

from erp.dashboard import build_dashboard

from .page import Page


@login_required
def dashboard(request):
    with Page(request, "dashboard") as page:
        include_profit = request.user.has_perm("erp.view_profit")
        data = build_dashboard(page.conn, page.lang, include_profit=include_profit)
        return page.render("erp/dashboard.html", **data)
