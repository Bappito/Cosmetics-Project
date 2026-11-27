"""When each open purchase order is due, for the week breakdown windows.

The balances themselves come from the shared services; this only adds dates to what they count.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from cosmetics_erp.formatting import format_date
from cosmetics_erp.services.where_used import WEEKS

from .page import Page

BEYOND = len(WEEKS)  # week index of an order due after the eight-week plan


def _when(page: Page, eta: date, today: date) -> str:
    """How far the date is from today, in words."""
    days = (eta - today).days
    if days == 0:
        return page.L("היום", "Today")
    if days == 1:
        return page.L("מחר", "Tomorrow")
    if days == -1:
        return page.L("באיחור של יום", "1 day late")
    if days < 0:
        return page.L(f"באיחור של {-days} ימים", f"{-days} days late")
    return page.L(f"בעוד {days} ימים", f"In {days} days")


def open_arrivals(page: Page, today: date | None = None) -> dict[str, list[dict]]:
    """Open orders per SKU, earliest first. Orders without a valid date come last."""
    today = today or date.today()
    out: dict[str, list[dict]] = defaultdict(list)
    for po_number, sku, units, grams, eta_text, item_type, status in page.conn.execute(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type, po.status "
        "FROM PurchaseOrders po JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled') ORDER BY po.eta_date, po.po_number"
    ).fetchall():
        eta = page.planning.parse_date(eta_text)
        week = page.planning.eta_to_week(eta_text)
        is_weight = item_type in ("RAW", "BULK")
        out[sku].append({
            "po": str(po_number),
            "amount": page.fmt(float((grams if is_weight else units) or 0), is_weight),
            "week_index": None if eta is None else (BEYOND if week is None else WEEKS.index(week)),
            "date": format_date(eta_text, is_he=page.is_he) if eta else page.L("ללא תאריך", "No date"),
            "when": _when(page, eta, today) if eta else "",
            "late": bool(eta and eta < today),
            "draft": status == "Draft",
        })
    for orders in out.values():
        orders.sort(key=lambda o: BEYOND + 1 if o["week_index"] is None else o["week_index"])
    return out


def _week_name(page: Page, index: int) -> str:
    if index >= BEYOND:
        return page.L("אחרי 8 השבועות", "after the 8 weeks")
    return page.periods[index][2]


def arrivals_for_week(page: Page, orders: list[dict], week_index: int) -> list[dict]:
    """What to show in one week's window.

    The orders counted in that week and the next one after it. If there are neither, the last
    earlier order, or an order that has no date.
    """
    dated = [o for o in orders if o["week_index"] is not None]
    now = [o for o in dated if o["week_index"] == week_index]
    later = [o for o in dated if o["week_index"] > week_index]
    shown = [
        {**o, "kind": "now", "tag": page.L("באיחור · נספר בשבוע הזה", "Late · counted in this week") if o["late"]
         else page.L("מגיע בשבוע הזה", "Arrives this week")}
        for o in now
    ]
    if later:
        week = _week_name(page, later[0]["week_index"])
        shown.append({**later[0], "kind": "next", "tag": page.L(f"ההגעה הבאה · {week}", f"Next arrival · {week}")})
    if shown:
        return shown
    if dated:
        week = _week_name(page, dated[-1]["week_index"])
        return [{**dated[-1], "kind": "past", "tag": page.L(f"כבר נספר ב{week}", f"Already counted in {week}")}]
    return [{**o, "kind": "past", "tag": page.L("לא נספר בתכנון", "Not counted in the plan")} for o in orders[:1]]
