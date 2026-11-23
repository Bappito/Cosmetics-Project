"""PRR (Project Readiness Review): each component's stock week by week, coloured by the readiness rule.

A product's tree is treated as its project. The balance uses every product that consumes a component,
so the colours match the warehouse picture everywhere else in the app.
"""
from __future__ import annotations

import csv

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from cosmetics_erp.services.where_used import COVERED, IDLE, READY, SHORT, WEEKS, readiness

from .page import Page

STATUS_LABELS = {
    READY: ("ירוק: מלאי קיים מספיק", "Green: stock on hand covers it"),
    COVERED: ("צהוב: חסר עד ההגעה", "Yellow: short until the arrival"),
    SHORT: ("אדום: חסר גם עם כל ההגעות", "Red: short even with all arrivals"),
    IDLE: ("ללא צורך השבוע", "Not needed this week"),
}


def _bom_rows(page: Page) -> list[dict]:
    rows = page.conn.execute("""
        SELECT b.component_sku, c.name AS comp_name, c.item_type AS comp_type,
               b.parent_sku, p.name AS parent_name,
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
    cols = ["component_sku", "comp_name", "comp_type", "parent_sku", "parent_name", "req_qty_units",
            "req_weight_grams", "avail_units", "avail_grams", *WEEKS]
    return [dict(zip(cols, r)) for r in rows]


def _project_view(page: Page, project: str):
    """Rows of one project's tree, each with its eight coloured weeks."""
    all_rows = _bom_rows(page)
    result = readiness(all_rows, page.inventory.get_incoming_map())
    project_rows = []
    counts = {READY: 0, COVERED: 0, SHORT: 0}
    for idx, row in enumerate(all_rows):
        if row["parent_sku"] != project:
            continue
        is_w = row["comp_type"] in ("RAW", "BULK")
        weeks = []
        for cell in result["cells"][idx]:
            if cell["status"] in counts:
                counts[cell["status"]] += 1
            weeks.append({
                **cell,
                "value": page.fmt(cell["after"], is_w),
                "title": page.L(
                    f"מלאי בלבד: {page.fmt(cell['stock_only'], is_w)} · נדרש: {page.fmt(cell['used'], is_w)}",
                    f"Stock only: {page.fmt(cell['stock_only'], is_w)} · needed: {page.fmt(cell['used'], is_w)}",
                ),
            })
        project_rows.append({
            "sku": row["component_sku"],
            "name": row["comp_name"],
            "type": row["comp_type"],
            "weeks": weeks,
            "stock": page.fmt(float(row["avail_grams"] if is_w else row["avail_units"]), is_w),
            "worst": min((w["status"] for w in weeks), key=lambda s: [SHORT, COVERED, READY, IDLE].index(s)),
        })
    return project_rows, counts


def _projects(page: Page) -> list[dict]:
    rows = page.conn.execute("""
        SELECT DISTINCT b.parent_sku, p.name FROM BOM b JOIN Catalog p ON b.parent_sku = p.sku ORDER BY b.parent_sku
    """).fetchall()
    return [{"sku": sku, "name": name or ""} for sku, name in rows]


@login_required
def prr(request):
    with Page(request, "prr") as page:
        projects = _projects(page)
        selected = request.GET.get("project") or (projects[0]["sku"] if projects else "")
        if selected and selected not in {p["sku"] for p in projects}:
            selected = projects[0]["sku"] if projects else ""
        query = request.GET.get("q", "").strip().casefold()
        rows, counts = _project_view(page, selected) if selected else ([], {READY: 0, COVERED: 0, SHORT: 0})
        if query:
            rows = [r for r in rows if query in r["sku"].casefold() or query in r["name"].casefold()]
        project_name = next((p["name"] for p in projects if p["sku"] == selected), "")
        return page.render(
            "erp/prr.html",
            title=page.L("PRR — מוכנות פרויקט", "PRR — project readiness"),
            subtitle=page.L(
                "לכל רכיב בעץ המוצר: מלאי שבועי לפי מוכנות. ירוק = מלאי קיים מספיק. צהוב = חסר עד הגעת הזמנת רכש. אדום = חסר גם עם כל ההגעות.",
                "For each component of the product tree: weekly stock by readiness. Green = stock on hand is enough. Yellow = short until a purchase order arrives. Red = short even with every arrival.",
            ),
            projects=projects,
            selected=selected,
            project_name=project_name,
            rows=rows,
            counts=counts,
            q=request.GET.get("q", ""),
            weeks=[{"code": p[0], "month": p[1], "label": p[2]} for p in page.periods],
            legend=[(k, page.L(*v)) for k, v in STATUS_LABELS.items()],
            export_url=f"/prr/export/?project={selected}",
        )


@login_required
def prr_export(request):
    """CSV of one project's readiness: one line per component and week."""
    with Page(request, "prr") as page:
        project = request.GET.get("project", "")
        rows, _ = _project_view(page, project)
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="prr-{project or "all"}.csv"'
        writer = csv.writer(response)
        writer.writerow(["SKU", "Item", "Week", "Status", "Stock after arrivals", "Stock without arrivals", "Needed"])
        for r in rows:
            for w in r["weeks"]:
                writer.writerow([r["sku"], r["name"], w["week"], w["status"],
                                 round(w["after"], 3), round(w["stock_only"], 3), round(w["used"], 3)])
        return response
