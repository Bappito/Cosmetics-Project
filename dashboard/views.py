from django.conf import settings
from django.shortcuts import render

from cosmetics_erp.db.connection import open_database
from cosmetics_erp.db.schema import init_db

from .data import build_dashboard
from .i18n import TEXT


def _language(request) -> str:
    lang = request.GET.get("lang") or request.COOKIES.get("lang") or "he"
    return lang if lang in TEXT else "he"


def dashboard(request):
    lang = _language(request)
    conn = open_database(str(settings.BUSINESS_DB_PATH))
    try:
        init_db(conn)
        context = build_dashboard(conn, lang == "he", TEXT[lang])
    finally:
        conn.close()
    context.update(t=TEXT[lang], lang=lang)
    response = render(request, "dashboard/index.html", context)
    response.set_cookie("lang", lang, max_age=60 * 60 * 24 * 365)
    return response
