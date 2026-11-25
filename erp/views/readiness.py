"""PRR (Project Readiness Review): each component's stock week by week, coloured by the readiness rule.

One screen with two views: production (bulk products and the raw materials they take) and
packaging (finished products and the bulk and packaging they take). The balance uses every
product that consumes a component, so the colours match the warehouse picture everywhere else.
"""
from __future__ import annotations

import csv
from collections import defaultdict

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse

from cosmetics_erp.services.where_used import COVERED, IDLE, READY, SHORT, WEEKS, readiness

from .page import Page

KINDS = {
    "production": ("BULK", "ייצור", "Production"),
    "packaging": ("FG", "אריזות", "Packaging"),
}
LEGEND = {
    READY: ("מלאי פיזי מכסה", "Physical stock covers it"),
    COVERED: ("מכוסה רק ע\"י משלוח", "Covered only by a delivery"),
    SHORT: ("חוסר", "Short"),
}
STATUS_PILL = {
    READY: ("מוכן", "Ready", "pill-closed"),
    COVERED: ("בתהליך", "In progress", "pill-open"),
    SHORT: ("חסר", "Short", "pill-bad"),
    IDLE: ("ללא צורך", "Not needed", ""),
}
CELL_CLASS = {READY: "prr-green", COVERED: "prr-yellow", SHORT: "prr-red", IDLE: "prr-none"}
SEVERITY = [SHORT, COVERED, READY, IDLE]


def _bom_rows(page: Page) -> list[dict]:
    rows = page.conn.execute("""
        SELECT b.component_sku, c.name AS comp_name, c.item_type AS comp_type,
               b.parent_sku, p.name AS parent_name, p.item_type AS parent_type,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               COALESCE(s.W1,0) AS W1, COALESCE(s.W2,0) AS W2, COALESCE(s.W3,0) AS W3, COALESCE(s.W4,0) AS W4,
               COALESCE(s.W5,0) AS W5, COALESCE(s.W6,0) AS W6, COALESCE(s.W7,0) AS W7, COALESCE(s.W8,0) AS W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        LEFT JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        ORDER BY b.component_sku, b.parent_sku
    """).fetchall()
    cols = ["component_sku", "comp_name", "comp_type", "parent_sku", "parent_name", "parent_type",
            "req_qty_units", "req_weight_grams", "avail_units", "avail_grams", *WEEKS]
    return [dict(zip(cols, r)) for r in rows]


def _supply_info(page: Page) -> dict:
    """Supplier and alternatives for each component."""
    info = {}
    for sku, supplier, alt_suppliers in page.conn.execute("SELECT sku, main_supplier, alt_suppliers FROM Catalog").fetchall():
        info[sku] = {"supplier": supplier or "", "alt_suppliers": alt_suppliers or "", "alt_skus": []}
    for sku, alt_sku in page.conn.execute("SELECT sku, alt_sku FROM AltSkus ORDER BY sku, priority").fetchall():
        info.setdefault(sku, {"supplier": "", "alt_suppliers": "", "alt_skus": []})["alt_skus"].append(alt_sku)
    return info


def _open_pos(page: Page) -> dict:
    """Open purchase orders per component, for the notes column."""
    out = defaultdict(list)
    for po_number, sku, eta in page.conn.execute(
        "SELECT po_number, sku, eta_date FROM PurchaseOrders WHERE status NOT IN ('Received', 'Cancelled') ORDER BY eta_date"
    ).fetchall():
        out[sku].append(f"{po_number} · {eta or '—'}")
    return out


def _kind_view(page: Page, kind: str):
    """One row per component of the products of this kind (production or packaging)."""
    parent_type = KINDS[kind][0]
    all_rows = _bom_rows(page)
    result = readiness(all_rows, page.inventory.get_incoming_map())
    supply = _supply_info(page)
    pos = _open_pos(page)

    parents = defaultdict(list)
    for row in all_rows:
        is_w = row["comp_type"] in ("RAW", "BULK")
        per = float(row["req_weight_grams"] if is_w else row["req_qty_units"] or 0)
        parents[row["component_sku"]].append({"sku": row["parent_sku"], "qty": page.fmt(per, is_w)})

    # Keep the rows of this kind; a component used by several of them is shown once, with its
    # balance after all of its users (the last row of that component).
    last_index: dict[str, int] = {}
    for idx, row in enumerate(all_rows):
        if row["parent_type"] == parent_type:
            last_index[row["component_sku"]] = idx

    # Who needs each component each week, across all products (for the cell details).
    usage: dict[str, list[list[dict]]] = defaultdict(lambda: [[] for _ in WEEKS])
    total_used: dict[str, list[float]] = defaultdict(lambda: [0.0] * len(WEEKS))
    for idx, row in enumerate(all_rows):
        if row["parent_type"] != parent_type:
            continue
        is_w_row = row["comp_type"] in ("RAW", "BULK")
        for w_i, cell in enumerate(result["cells"][idx]):
            total_used[row["component_sku"]][w_i] += cell["used"]
            if cell["used"] > 1e-9:
                usage[row["component_sku"]][w_i].append({"parent": row["parent_sku"], "used": page.fmt(cell["used"], is_w_row)})
    counts = {READY: 0, COVERED: 0, SHORT: 0}
    out = []
    for sku, idx in last_index.items():
        row = all_rows[idx]
        is_w = row["comp_type"] in ("RAW", "BULK")
        weeks = []
        for w_i, cell in enumerate(result["cells"][idx]):
            if cell["status"] in counts:
                counts[cell["status"]] += 1
            inc = cell.get("incoming")
            arriving = float(inc["amt"]) if inc else 0.0
            # The last row's balance is after every product's use, so the week's need is the sum over all products.
            need = total_used[sku][w_i]
            before = cell["after"] + need - arriving
            weeks.append({
                **cell,
                "css": CELL_CLASS[cell["status"]],
                "value": page.fmt(cell["after"], is_w),
                "week_label": page.periods[w_i][2],
                "before_text": page.fmt(before, is_w),
                "used_text": page.fmt(need, is_w),
                "incoming_text": page.fmt(arriving, is_w) if inc else "",
                "incoming_pos": ", ".join(inc["pos"]) if inc and isinstance(inc.get("pos"), list) else (inc or {}).get("pos", "") if inc else "",
                "breakdown": usage[sku][w_i],
                "title": "",
            })
        worst = min((w["status"] for w in weeks), key=SEVERITY.index)
        info = supply.get(sku, {"supplier": "", "alt_suppliers": "", "alt_skus": []})
        pill_he, pill_en, pill_css = STATUS_PILL[worst]
        out.append({
            "sku": sku,
            "name": row["comp_name"],
            "type": row["comp_type"],
            "supplier": info["supplier"],
            "alt": ", ".join([*info["alt_skus"], info["alt_suppliers"]]).strip(", "),
            "parents": parents.get(sku, []),
            "stock": page.fmt(float(row["avail_grams"] if is_w else row["avail_units"] or 0), is_w),
            "pos": " · ".join(pos.get(sku, [])),
            "weeks": weeks,
            "worst": worst,
            "status_label": pill_he if page.is_he else pill_en,
            "status_css": pill_css,
        })
    return out, counts


def _month_groups(weeks: list[dict]) -> list[dict]:
    groups: list[dict] = []
    for w in weeks:
        if groups and groups[-1]["label"] == w["month"]:
            groups[-1]["span"] += 1
        else:
            groups.append({"label": w["month"], "span": 1})
    return groups


def _filtered(page: Page, request, kind: str):
    rows, counts = _kind_view(page, kind)
    query = request.GET.get("q", "").strip().casefold()
    if query:
        rows = [r for r in rows if query in r["sku"].casefold() or query in r["name"].casefold()
                or query in r["supplier"].casefold()]
    product = request.GET.get("product", "")
    if product:
        rows = [r for r in rows if any(p["sku"] == product for p in r["parents"])]
    return rows, counts


def _kind_from(request) -> str:
    kind = request.GET.get("kind", "production")
    return kind if kind in KINDS else "production"


@login_required
def prr(request):
    """PRR with a switch between production and packaging."""
    kind = _kind_from(request)
    with Page(request, "prr") as page:
        rows, counts = _filtered(page, request, kind)
        products = sorted({p["sku"] for r in rows for p in r["parents"]})
        names = dict(page.conn.execute("SELECT sku, name FROM Catalog").fetchall())
        weeks = [{"code": p[0], "month": p[1], "label": p[2]} for p in page.periods]
        base = f"?kind={kind}"
        return page.render(
            "erp/prr.html",
            title=page.L("PRR — מוכנות פרויקט", "PRR — project readiness"),
            subtitle=page.L(
                "מעקב מקטים וסטטוסים: לכל רכיב, מלאי שבועי, מי משתמש בו, הספק וההזמנות הפתוחות.",
                "SKU and status tracking: for each component, weekly stock, who uses it, the supplier and open orders.",
            ),
            kind=kind,
            kinds=[
                {"key": "production", "label": page.L("ייצור", "Production")},
                {"key": "packaging", "label": page.L("אריזות", "Packaging")},
            ],
            product=request.GET.get("product", ""),
            product_options=[{"sku": s, "label": f"{s} - {names.get(s, '')}"} for s in products],
            rows=rows,
            counts=counts,
            q=request.GET.get("q", ""),
            weeks=weeks,
            month_groups=_month_groups(weeks),
            legend=[(k, page.L(*v)) for k, v in LEGEND.items()],
            export_url=f"{reverse('prr_export')}{base}",
            short_export_url=f"{reverse('prr_export')}{base}&only=short",
        )


@login_required
def prr_packaging(request):
    """Old address of the packaging PRR: now a tab on the PRR screen."""
    return HttpResponseRedirect(f"{reverse('prr')}?kind=packaging")


@login_required
def prr_export(request):
    """CSV of the PRR view: one line per component and week. ?only=short keeps only the shortages."""
    kind = _kind_from(request)
    with Page(request, "prr") as page:
        rows, _ = _filtered(page, request, kind)
        if request.GET.get("only") == "short":
            rows = [r for r in rows if r["worst"] == SHORT]
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="prr-{kind}.csv"'
        writer = csv.writer(response)
        writer.writerow(["SKU", "Item", "Supplier", "Week", "Status", "Stock after arrivals", "Stock without arrivals", "Needed"])
        for r in rows:
            for w in r["weeks"]:
                writer.writerow([r["sku"], r["name"], r["supplier"], w["week"], w["status"],
                                 round(w["after"], 3), round(w["stock_only"], 3), round(w["used"], 3)])
        return response
