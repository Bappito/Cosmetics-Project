from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render

from cosmetics_erp.db.connection import open_database
from cosmetics_erp.db.schema import init_db

from .data import build_dashboard
from .i18n import TEXT


def _language(request) -> str:
    lang = request.GET.get("lang") or request.COOKIES.get("lang") or "he"
    return lang if lang in TEXT else "he"


@login_required
@permission_required("dashboard.view_dashboard", raise_exception=True)
def dashboard(request):
    lang = _language(request)
    show_profit = request.user.has_perm("dashboard.view_profit")
    conn = open_database(str(settings.BUSINESS_DB_PATH))
    try:
        init_db(conn)
        context = build_dashboard(conn, lang == "he", TEXT[lang], include_profit=show_profit)
    finally:
        conn.close()
    context.update(t=TEXT[lang], lang=lang, show_profit=show_profit, user=request.user)
    response = render(request, "dashboard/index.html", context)
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response


class DashboardLoginView(auth_views.LoginView):
    """Login page in the same language rules as the dashboard."""

    template_name = "dashboard/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        lang = _language(self.request)
        context.update(t=TEXT[lang], lang=lang)
        return context
