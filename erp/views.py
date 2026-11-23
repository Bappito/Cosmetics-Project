from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.urls import reverse

from .bridge import open_erp_connection
from .dashboard import build_dashboard
from .screens import SCREENS

LANGS = ("he", "en")


def _nav(user, active: str, lang: str) -> list[dict]:
    """Sidebar entries. A screen appears only if the user may view it; unported screens are greyed out."""
    items = []
    for key, (he, en, ported) in SCREENS.items():
        if not user.has_perm(f"erp.view_{key}"):
            continue
        items.append({
            "label": he if lang == "he" else en,
            "url": reverse("dashboard") if ported and key == "dashboard" else None,
            "active": key == active,
            "ported": ported,
        })
    return items


@login_required
@permission_required("erp.view_dashboard", raise_exception=True)
def dashboard(request):
    lang = request.session.get("lang", "he")
    if lang not in LANGS:
        lang = "he"
    include_profit = request.user.has_perm("erp.view_profit")
    conn = open_erp_connection()
    try:
        data = build_dashboard(conn, lang, include_profit=include_profit)
    finally:
        conn.close()
    data["nav"] = _nav(request.user, "dashboard", lang)
    return render(request, "erp/dashboard.html", data)


def set_language(request, lang: str):
    if lang in LANGS:
        request.session["lang"] = lang
    return redirect(request.META.get("HTTP_REFERER") or reverse("dashboard"))
