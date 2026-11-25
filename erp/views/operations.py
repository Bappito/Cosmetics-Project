"""Settings toggles, undo, the change log and the quick command agent."""
from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from cosmetics_erp.services.quick_command import CommandError, added_base_amount, check_unit_for_type, parse_command

from .page import LANGS, THEMES, UNITS, Page, safe_next

COMMAND_PENDING = "quick_command"


# Settings: language, weight unit and theme are stored in the session.

@require_POST
def set_language(request, lang: str):
    if lang in LANGS:
        request.session["lang"] = lang
    return redirect(safe_next(request, reverse("dashboard")))


@require_POST
def set_unit(request, unit: str):
    if unit in UNITS:
        request.session["unit"] = unit
    return redirect(safe_next(request, reverse("dashboard")))


@require_POST
def set_theme(request, theme: str):
    if theme in THEMES:
        request.session["theme"] = theme
    return redirect(safe_next(request, reverse("dashboard")))


@login_required
@require_POST
def undo(request, screen: str, scope: str):
    """Restore the last backup of a scope (stock or schedule)."""
    with Page(request, screen, edit=True) as page:
        if scope not in ("stock", "schedule"):
            return HttpResponseNotAllowed([])
        done = page.backups.undo_last(scope)
        if done:
            page.flash(page.L(f"שוחזר המצב שלפני: {done}", f"Restored the state before: {done}"))
        else:
            page.error(page.L("אין גיבוי זמין לשחזור", "No backup available to restore"))
    return redirect(safe_next(request, reverse(screen)))


@login_required
def audit(request):
    with Page(request, "audit") as page:
        rows = page.conn.execute(
            "SELECT at, scope, action FROM AuditLog ORDER BY audit_id DESC LIMIT 300"
        ).fetchall()
        area = {"stock": page.L("מלאי ועצים", "Stock & trees"), "schedule": page.L("תכנון", "Planning")}
        entries = [{"time": at, "area": area.get(scope, scope), "action": action} for at, scope, action in rows]
        return page.render(
            "erp/audit.html",
            title=page.L("יומן שינויים", "Change log"),
            subtitle=page.L(
                "כל שינוי במלאי, בעצי המוצר ובתכנון נרשם כאן, כולל ביטולים. היומן לא נמחק אוטומטית.",
                "Every change to stock, product trees and planning is recorded here, including undos. The log is never trimmed automatically.",
            ),
            entries=entries,
        )


def _command_error_text(page: Page, key: str, sku: str | None = None) -> str:
    texts = {
        "need_two_numbers": page.L("הפקודה צריכה לכלול כמות, יחידה ומק\"ט.", "The command must include a quantity, unit, and SKU."),
        "not_positive": page.L("הכמות חייבת להיות גדולה מאפס.", "The quantity must be greater than zero."),
        "sku_missing": page.L(f"מק\"ט {sku} לא קיים בקטלוג.", f"SKU {sku} was not found in the catalog."),
        "weight_needs_unit": page.L("למק\"ט משקלי יש לציין קילו או גרם.", "For a weight-based SKU, specify kg or grams."),
        "units_needed": page.L("למק\"ט יחידות יש לציין יחידות (units).", "For a unit-based SKU, specify units."),
        "unit_whole_numbers": page.L("כמות ביחידות חייבת להיות מספר שלם.", "Unit quantities must be whole numbers."),
        "sku_removed": page.L("המק\"ט הוסר מהקטלוג. בטל/י את הפקודה.", "The SKU was removed from the catalog. Cancel this command."),
    }
    return texts[key]


@login_required
def quick_command(request):
    with Page(request, "quick_command") as page:
        if request.method == "POST":
            action = request.POST.get("action", "")
            if action == "submit":
                _submit_command(page, request.POST.get("command", "").strip())
            elif action == "confirm":
                _apply_command(page)
            elif action == "cancel":
                page.clear_pending(COMMAND_PENDING)
            return redirect("quick_command")

        pending = page.pending(COMMAND_PENDING)
        preview = None
        if pending:
            current = page.conn.execute(
                "SELECT qty_units, weight_grams FROM Catalog WHERE sku=?", (pending["sku"],)
            ).fetchone()
            if current is None:
                page.error(_command_error_text(page, "sku_removed"))
            else:
                is_weight = pending["is_weight"]
                current_base = float(current[1] if is_weight else current[0])
                preview = {
                    **pending,
                    "amount_text": f"{pending['amount']:g} {pending['unit']}",
                    "current_text": page.fmt(current_base, is_weight),
                    "next_text": page.fmt(current_base + pending["added_base"], is_weight),
                }
        return page.render(
            "erp/quick_command.html",
            title=page.L("סוכן פקודות מהיר", "Quick command agent"),
            subtitle=page.L(
                "הזן/י כמות ויחידה מפורשות ואחריהן מק\"ט, לדוגמה: `הוסף 5 קילו ל-1001` או `הוסף 300 יחידות ל-3001`.",
                "Enter an amount and explicit unit followed by an SKU, e.g. `add 5 kg to 1001` or `add 300 units to 3001`.",
            ),
            preview=preview,
            pending_missing=pending is not None and preview is None,
            undo_available=page.last_backup("stock") is not None,
        )


def _submit_command(page: Page, text: str) -> None:
    try:
        parsed = parse_command(text)
    except CommandError as exc:
        page.error(_command_error_text(page, exc.key))
        return
    item = page.conn.execute(
        "SELECT name, item_type FROM Catalog WHERE sku=?", (parsed["sku"],)
    ).fetchone()
    if not item:
        page.error(_command_error_text(page, "sku_missing", parsed["sku"]))
        return
    name, item_type = item
    try:
        check_unit_for_type(item_type, parsed["unit"], parsed["amount"])
    except CommandError as exc:
        page.error(_command_error_text(page, exc.key))
        return
    page.set_pending(COMMAND_PENDING, {
        "sku": parsed["sku"],
        "name": name,
        "item_type": item_type,
        "amount": parsed["amount"],
        "unit": parsed["unit"],
        "added_base": added_base_amount(parsed["amount"], parsed["unit"]),
        "is_weight": item_type in ("RAW", "BULK"),
        "command": text,
    })


def _apply_command(page: Page) -> None:
    pending = page.pending(COMMAND_PENDING)
    if not pending:
        return
    if not page.request.POST.get("confirmed"):
        page.error(page.L("יש לאשר את השינוי לפני העדכון.", "Confirm the change before updating stock."))
        return
    if page.conn.execute("SELECT 1 FROM Catalog WHERE sku=?", (pending["sku"],)).fetchone() is None:
        page.error(_command_error_text(page, "sku_removed"))
        return
    page.push_backup("stock", f"{page.L('פקодת מלאי', 'Stock command')}: {pending['command'][:40]}")
    column = "weight_grams" if pending["is_weight"] else "qty_units"
    page.conn.execute(f"UPDATE Catalog SET {column} = {column} + ? WHERE sku=?", (pending["added_base"], pending["sku"]))
    page.conn.commit()
    page.inventory.reconcile_batches()
    page.clear_pending(COMMAND_PENDING)
    page.flash(page.L(
        f"נוספו {pending['amount']:g} {pending['unit']} למק\"ט {pending['sku']}.",
        f"Added {pending['amount']:g} {pending['unit']} to SKU {pending['sku']}.",
    ))
