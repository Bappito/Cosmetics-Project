"""Shared plumbing for the ERP screens: permissions, the business database, labels and messages.

Each screen view opens a ``Page`` as a context manager. It opens the ERP SQLite connection for the
request, checks the screen permission, and gives the view the translated labels and the number
formatting that follow the user's weight unit setting.
"""
from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from cosmetics_erp.config import Localization
from cosmetics_erp.formatting import format_value
from cosmetics_erp.services.backups import BackupService
from cosmetics_erp.services.inventory import InventoryService
from cosmetics_erp.services.planning import PlanningService, get_plan_start
from erp.bridge import open_erp_connection
from erp.screens import SCREENS
from erp.strings import UI

LANGS = ("he", "en")
UNITS = ("kg", "g")
THEMES = ("light", "dark")

URL_NAMES = {key: key for key in SCREENS}  # each screen key is also its URL name


def nav_items(user, active: str, lang: str) -> list[dict]:
    """Sidebar entries. A screen appears only if the user may view it."""
    items = []
    for key, (he, en) in SCREENS.items():
        if not user.has_perm(f"erp.view_{key}"):
            continue
        items.append({
            "key": key,
            "label": he if lang == "he" else en,
            "url": reverse(URL_NAMES[key]),
            "active": key == active,
        })
    return items


def safe_next(request, default: str) -> str:
    """Where to go after a form. Only a path on this site is allowed."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return default


class Page:
    """One screen request. Use as ``with Page(request, "inventory") as page:``."""

    def __init__(self, request, screen: str, *, edit: bool = False) -> None:
        if screen not in SCREENS:
            raise ValueError(f"unknown screen: {screen}")
        action = "edit" if edit else "view"
        if not request.user.has_perm(f"erp.{action}_{screen}"):
            raise PermissionDenied
        self.request = request
        self.screen = screen
        self.lang = request.session.get("lang", "he")
        if self.lang not in LANGS:
            self.lang = "he"
        self.unit = request.session.get("unit", "kg")
        if self.unit not in UNITS:
            self.unit = "kg"
        self.theme = request.session.get("theme", "light")
        self.use_kg = self.unit == "kg"
        self.w_factor = 1000.0 if self.use_kg else 1.0
        self.w_label = ("ק\"ג" if self.lang == "he" else "kg") if self.use_kg else ("גרם" if self.lang == "he" else "g")
        self.u_label = "יח'" if self.lang == "he" else "u"

    def __enter__(self) -> "Page":
        self.conn = open_erp_connection()
        self.plan_start = get_plan_start(self.conn)
        self.i18n = Localization(self.lang, self.plan_start)
        self.is_he = self.i18n.is_he
        self.L = self.i18n.translate
        self.periods = self.i18n.plan_periods
        self.planning = PlanningService(self.periods, self.L, plan_start=self.plan_start)
        self.inventory = InventoryService(self.conn, self.L, self.planning.parse_date, self.planning.eta_to_week)
        self.backups = BackupService(self.conn)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.conn.close()

    # Formatting

    def fmt(self, value: float, is_weight: bool) -> str:
        return format_value(
            value, is_weight, use_kg=self.use_kg, w_factor=self.w_factor,
            w_label=self.w_label, u_label=self.u_label,
        )

    def unit_for(self, is_weight: bool) -> str:
        return self.w_label if is_weight else self.u_label

    # Responses

    def render(self, template: str, **data):
        context = {
            "screen": self.screen,
            "nav": nav_items(self.request.user, self.screen, self.lang),
            "is_he": self.is_he,
            "L": self.L,
            "periods": self.periods,
            "w_label": self.w_label,
            "u_label": self.u_label,
            "unit": self.unit,
            "theme": self.theme,
            "ui_text": UI[self.lang],
            "plan_start": self.plan_start,
            "next_unit": "g" if self.unit == "kg" else "kg",
            "next_theme": "light" if self.theme == "dark" else "dark",
        }
        context.update(data)
        return render(self.request, template, context)

    # Messages

    def flash(self, text: str) -> None:
        messages.success(self.request, text)

    def error(self, text: str) -> None:
        messages.error(self.request, text)

    def warn(self, text: str) -> None:
        messages.warning(self.request, text)

    # Backups and undo

    def push_backup(self, scope: str, label: str) -> None:
        self.backups.push_backup(scope, label)

    def last_backup(self, scope: str):
        return self.backups.last_backup(scope)

    # Review-then-confirm state. Session data must stay JSON-serializable.

    def pending(self, name: str):
        return self.request.session.get(f"pending:{name}")

    def set_pending(self, name: str, value) -> None:
        self.request.session[f"pending:{name}"] = value
        self.request.session.modified = True

    def clear_pending(self, name: str) -> None:
        self.request.session.pop(f"pending:{name}", None)
        self.request.session.modified = True

    def batch_exists(self, sku: str, batch_no: str) -> bool:
        return self.inventory.batch_exists(sku, batch_no)
