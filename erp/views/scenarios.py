"""Personal what-if simulator: each user's private scenarios of planned orders, with the shortages they cause."""
from __future__ import annotations

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect
from django.urls import reverse

from cosmetics_erp.services.bom import PARENT_TYPES
from cosmetics_erp.services.mrp import WEEKS
from cosmetics_erp.services.scenario import scenario_shortages
from erp.models import Scenario

from .page import Page

EDIT_NEW_ROWS = 3
WEIGHT_TYPES = ("RAW", "BULK")


def _open_po_frame(page: Page) -> pd.DataFrame:
    po_rows = pd.read_sql(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled')",
        page.conn,
    )
    po_rows["qty_base"] = [
        float(w if t in WEIGHT_TYPES else u or 0.0)
        for w, u, t in zip(po_rows["order_weight_grams"], po_rows["order_qty_units"], po_rows["item_type"])
    ]
    po_rows["week"] = po_rows["eta_date"].map(page.planning.eta_to_week)
    return po_rows


def _parse_lines(post) -> tuple[list[dict], list[str]]:
    count = int(post.get("row_count", "0") or 0)
    lines, errors = [], []
    for i in range(count):
        sku = post.get(f"line_sku_{i}", "").strip()
        qty_text = post.get(f"line_qty_{i}", "").strip()
        if not sku and not qty_text:
            continue
        try:
            qty = float(qty_text.replace(",", ""))
            week = int(post.get(f"line_week_{i}", "1"))
        except ValueError:
            errors.append(f"שורה {i + 1}: כמות או שבוע לא תקינים")
            continue
        if not sku or qty <= 0 or not 1 <= week <= len(WEEKS):
            errors.append(f"שורה {i + 1}: צריך מוצר, שבוע ו-כמות גדולה מאפס")
            continue
        lines.append({"sku": sku, "week": week, "qty": qty})
    return lines, errors


def _visible_scenario(request, scenario_id: int) -> Scenario:
    try:
        return Scenario.objects.get(Q(pk=scenario_id) & (Q(owner=request.user) | Q(shared=True)))
    except Scenario.DoesNotExist:
        raise Http404("scenario not found")


def _own_scenario(request, scenario_id: int) -> Scenario:
    try:
        return Scenario.objects.get(pk=scenario_id, owner=request.user)
    except Scenario.DoesNotExist:
        raise Http404("scenario not found")


@login_required
def scenarios(request):
    if request.method == "POST":
        with Page(request, "scenarios", edit=True) as page:
            action = request.POST.get("action", "")
            if action == "create":
                name = request.POST.get("name", "").strip() or page.L("תרחיש חדש", "New scenario")
                scenario = Scenario.objects.create(owner=request.user, name=name[:120])
                return redirect(f"{reverse('scenarios')}?id={scenario.pk}")
            if action in ("save", "toggle_share", "delete", "rename"):
                scenario = _own_scenario(request, int(request.POST.get("scenario_id", "0") or 0))
                if action == "save":
                    lines, errors = _parse_lines(request.POST)
                    if errors:
                        for e in errors:
                            page.error(e)
                    else:
                        scenario.lines = lines
                        scenario.save()
                        page.flash(page.L("התרחיש נשמר.", "Scenario saved."))
                elif action == "rename":
                    scenario.name = (request.POST.get("name", "").strip() or scenario.name)[:120]
                    scenario.save()
                elif action == "toggle_share":
                    scenario.shared = not scenario.shared
                    scenario.save()
                    page.flash(page.L("התרחיש משותף לכולם לצפייה.", "Scenario shared for viewing.") if scenario.shared
                               else page.L("התרחיש פרטי שוב.", "Scenario is private again."))
                elif action == "delete":
                    scenario.delete()
                    page.flash(page.L("התרחיש נמחק.", "Scenario deleted."))
                    return redirect("scenarios")
                return redirect(f"{reverse('scenarios')}?id={scenario.pk}")
        return redirect("scenarios")

    with Page(request, "scenarios") as page:
        L = page.L
        mine = list(Scenario.objects.filter(owner=request.user))
        others = list(Scenario.objects.filter(shared=True).exclude(owner=request.user).select_related("owner"))
        selected = None
        sid = request.GET.get("id")
        if sid:
            selected = _visible_scenario(request, int(sid))
        is_owner = bool(selected and selected.owner_id == request.user.pk)

        catalog = pd.read_sql(
            "SELECT sku, name, item_type, qty_units, weight_grams, min_order_qty, main_supplier, primary_warehouse FROM Catalog",
            page.conn,
        )
        bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", page.conn)
        products = [{"sku": r.sku, "label": f"{r.sku} - {r.name}", "type": r.item_type}
                    for r in catalog[catalog["item_type"].isin(PARENT_TYPES)].sort_values(["item_type", "sku"]).itertuples()]

        result_rows, line_rows = [], []
        if selected:
            lines = selected.lines or []
            if is_owner:
                line_rows = lines + [{"sku": "", "week": 1, "qty": ""} for _ in range(EDIT_NEW_ROWS)]
            else:
                line_rows = lines
            suggestions = scenario_shortages(catalog, bom, _open_po_frame(page), lines)
            for r in suggestions.itertuples():
                is_w = r.item_type in WEIGHT_TYPES
                result_rows.append({
                    "sku": r.sku,
                    "name": r.name,
                    "type": r.item_type,
                    "week": f"{L('שבוע', 'Week')} {r.need_week[1:]}",
                    "now": r.need_week == "W1",
                    "short": page.fmt(float(r.shortfall_base), is_w),
                    "order": page.fmt(float(r.order_base), is_w),
                    "supplier": r.supplier or "",
                })

        return page.render(
            "erp/scenarios.html",
            title=L("סימולטור אישי", "My simulator"),
            subtitle=L("תרחיש פרטי שלך: הזמנות מתוכננות לפי שבוע, מול המלאי וההזמנות הפתוחות. רק אתה רואה אותו עד שתשתף.",
                       "Your private scenario: planned orders by week, against stock and open orders. Only you see it until you share it."),
            mine=mine,
            others=others,
            selected=selected,
            is_owner=is_owner,
            products=products,
            weeks=[{"value": i + 1, "label": f"{L('שבוע', 'Week')} {i + 1}"} for i in range(len(WEEKS))],
            line_rows=line_rows,
            result_rows=result_rows,
            shortage_count=len(result_rows),
            here=request.get_full_path(),
        )
