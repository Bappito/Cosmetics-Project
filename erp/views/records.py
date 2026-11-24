"""Read-only lists: projects, alternative SKUs and shipments (demo data, see cosmetics_erp/db/records.py)."""
from __future__ import annotations

import pandas as pd
from django.contrib.auth.decorators import login_required

from cosmetics_erp.formatting import format_date

from .page import Page


def _blank(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def _render_list(page: Page, title: str, subtitle: str, headers: list[str], rows: list[list[str]], metrics: list[dict]):
    return page.render(
        "erp/record_list.html",
        title=title,
        subtitle=subtitle,
        metrics=metrics,
        headers=headers,
        rows=rows,
        count=len(rows),
    )


@login_required
def projects(request):
    with Page(request, "projects") as page:
        L = page.L
        df = pd.read_sql(
            "SELECT p.*, c.name AS item_name FROM Projects p LEFT JOIN Catalog c ON p.sku = c.sku ORDER BY p.due_date",
            page.conn,
        )
        rows = [[
            r.code, r.name, _blank(r.customer), _blank(r.sku), _blank(r.item_name),
            r.status, format_date(r.start_date, is_he=page.is_he), format_date(r.due_date, is_he=page.is_he),
        ] for r in df.itertuples()]
        headers = [L("קוד", "Code"), L("פרויקט", "Project"), L("לקוח", "Customer"),
                   L('מק"ט', "SKU"), L("שם פריט", "Item"), L("סטטוס", "Status"),
                   L("התחלה", "Start"), L("יעד", "Due")]
        return _render_list(
            page,
            L("פרויקטים", "Projects"),
            L("פרויקטי השקה ושינוי, עם המוצר המקושר ותאריך היעד.", "Launch and change projects, with the linked product and due date."),
            headers, rows,
            [
                {"label": L('סה"כ פרויקטים', "Total projects"), "value": len(df)},
                {"label": L("פעילים", "Active"), "value": int((df["status"] == "Active").sum())},
                {"label": L("בהמתנה", "On hold"), "value": int((df["status"] == "On hold").sum())},
                {"label": L("הושלמו", "Done"), "value": int((df["status"] == "Done").sum())},
            ],
        )


@login_required
def alt_skus(request):
    with Page(request, "alt_skus") as page:
        L = page.L
        df = pd.read_sql(
            "SELECT a.*, c.name AS item_name FROM AltSkus a LEFT JOIN Catalog c ON a.sku = c.sku ORDER BY a.sku, a.priority",
            page.conn,
        )
        rows = [[r.sku, _blank(r.item_name), r.alt_sku, _blank(r.description), str(int(r.priority))]
                for r in df.itertuples()]
        headers = [L('מק"ט', "SKU"), L("שם פריט", "Item"), L('מק"ט חלופי', "Alternative SKU"),
                   L("תיאור", "Description"), L("עדיפות", "Priority")]
        return _render_list(
            page,
            L("מקטים חלופיים", "Alternative SKUs"),
            L("מקטים שניתן להשתמש בהם במקום המקט הראשי, לפי סדר העדיפות.",
              "SKUs that can be used in place of the main SKU, in priority order."),
            headers, rows,
            [
                {"label": L('סה"כ שורות', "Total rows"), "value": len(df)},
                {"label": L("מקטים ראשיים", "Main SKUs"), "value": int(df["sku"].nunique())},
            ],
        )


@login_required
def shipments(request):
    with Page(request, "shipments") as page:
        L = page.L
        df = pd.read_sql("SELECT * FROM Shipments ORDER BY ship_date DESC, shipment_id DESC", page.conn)
        rows = [[
            r.shipment_no, _blank(r.customer), _blank(r.carrier), _blank(r.ship_type), _blank(r.sku),
            f"{float(r.qty_units):,.0f}", format_date(r.ship_date, is_he=page.is_he), r.status,
        ] for r in df.itertuples()]
        headers = [L("משלוח", "Shipment"), L("לקוח", "Customer"), L("חברת הובלה", "Carrier"),
                   L("סוג משלוח", "Shipment type"), L('מק"ט', "SKU"), L("כמות", "Qty"),
                   L("תאריך", "Date"), L("סטטוס", "Status")]
        return _render_list(
            page,
            L("משלוחים", "Shipments"),
            L("מעקב משלוחים לפי לקוח, סוג משלוח וסטטוס.", "Track shipments by customer, shipment type and status."),
            headers, rows,
            [
                {"label": L('סה"כ משלוחים', "Total shipments"), "value": len(df)},
                {"label": L("נמסרו", "Delivered"), "value": int((df["status"] == "Delivered").sum())},
                {"label": L("בדרך", "In transit"), "value": int((df["status"] == "In transit").sum())},
                {"label": L("מתוכננים", "Planned"), "value": int((df["status"] == "Planned").sum())},
            ],
        )
