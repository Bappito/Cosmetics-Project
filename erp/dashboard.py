"""Dashboard screen: the web version of cosmetics_erp/ui/pages/dashboard.py.

The calculations use the same services as the Streamlit app. Only the presentation differs.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from cosmetics_erp.config import Localization
from cosmetics_erp.services.capacity import packable_units
from cosmetics_erp.services.costing import product_margins
from cosmetics_erp.services.planning import PlanningService

EXPIRY_WARNING_DAYS = 30


def _format_date(value, is_he: bool) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "<na>"}:
        return "—"
    try:
        parsed = date.fromisoformat(text[:10])
    except ValueError:
        return text
    return parsed.strftime("%d/%m/%Y") if is_he else parsed.strftime("%b %d, %Y")


def _format_qty(value: float, weighted: bool, unit_label: str, weight_label: str) -> str:
    if weighted:
        return f"{value:,.0f} {weight_label}"
    return f"{value:,.0f} {unit_label}"


def _table(headers: list[str], rows: list[list[str]]) -> dict:
    return {"headers": headers, "rows": rows}


def build_dashboard(conn, lang: str) -> dict:
    i18n = Localization(lang)
    L = i18n.translate
    is_he = i18n.is_he

    cat = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams, item_price FROM Catalog", conn)
    bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", conn)
    batches = pd.read_sql(
        "SELECT b.sku, c.name AS name, c.item_type AS item_type, b.batch_no, b.qty_units, b.weight_grams, b.expiry_date "
        "FROM Batches b LEFT JOIN Catalog c ON b.sku = c.sku WHERE b.status = 'Active'",
        conn,
    )
    pos = pd.read_sql(
        "SELECT po.po_number, po.sku, c.name AS name, po.supplier, po.eta_date, po.status "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
        "WHERE po.status NOT IN ('Received', 'Cancelled') ORDER BY po.eta_date",
        conn,
    )

    parse_date = PlanningService.parse_date
    today = date.today()
    soon_limit = today + timedelta(days=EXPIRY_WARNING_DAYS)
    batches["exp"] = batches["expiry_date"].map(parse_date)
    expired = batches[batches["exp"].notna() & (batches["exp"] < today)]
    expiring = batches[batches["exp"].notna() & (batches["exp"] >= today) & (batches["exp"] <= soon_limit)]

    metrics = [
        {"label": L("הזמנות רכש פתוחות", "Open purchase orders"), "value": len(pos)},
        {"label": L(f"אצוות שפגות ב-{EXPIRY_WARNING_DAYS} ימים", f"Batches expiring in {EXPIRY_WARNING_DAYS} days"), "value": len(expiring)},
        {"label": L("אצוות שפג תוקפן", "Expired active batches"), "value": len(expired)},
    ]

    # Packable units
    capacity = packable_units(cat, bom)
    capacity_block = {"title": L("כמה יחידות ניתן לארוז עכשיו", "Units that can be packed now"), "warning": None, "table": None, "empty": None}
    if capacity.empty:
        capacity_block["empty"] = L("אין מוצרים סופיים בקטלוג.", "No finished products in the catalog.")
    else:
        short = int((capacity["packable_units"] == 0).sum())
        if short:
            capacity_block["warning"] = L(
                f"אי אפשר לארוז {short} מוצרים כרגע בגלל חוסר ברכיב.",
                f"{short} products cannot be packed right now because a component is short.",
            )
        capacity_block["table"] = _table(
            [L("מק\"ט", "SKU"), L("פריט", "Item"), L("ניתן לארוז (יח')", "Can pack (units)"), L("הרכיב המגביל", "Limiting component")],
            [
                [str(r.sku), str(r.name), f"{int(r.packable_units):,}", str(r.limiting_component)]
                for r in capacity.itertuples()
            ],
        )

    # Margins
    margins = product_margins(cat, bom)
    margin_block = {"title": L("רווח משוער מכל מוצר סופי", "Estimated profit per finished product"), "table": None, "empty": None, "note": None}
    if margins.empty:
        margin_block["empty"] = L("אין מוצרים סופיים בקטלוג.", "No finished products in the catalog.")
    else:
        margin_block["table"] = _table(
            [
                L("מק\"ט", "SKU"),
                L("פריט", "Item"),
                L("מחיר מכירה", "Price"),
                L("עלות", "Cost"),
                L("רווח ליחידה", "Profit / unit"),
                L("רווח %", "Margin %"),
                L("מלאי (יח')", "Stock (units)"),
                L("רווח צפוי מהמלאי", "Profit on stock"),
            ],
            [
                [
                    str(r.sku),
                    "" if pd.isna(r.name) else str(r.name),
                    f"₪{r.price:,.2f}",
                    f"₪{r.cost:,.2f}",
                    f"₪{r.margin:,.2f}",
                    "—" if pd.isna(r.margin_pct) else f"{r.margin_pct:,.1f}%",
                    f"{r.stock_units:,.0f}",
                    f"₪{r.stock_margin:,.0f}",
                ]
                for r in margins.itertuples()
            ],
        )
        margin_block["note"] = L(
            "העלות מחושבת לפי ה-BOM ומחירי הקטלוג. מחיר המכירה הוא item_price של המוצר הסופי.",
            "Cost is calculated from the BOM and catalog prices. Selling price is the finished product's item_price.",
        )

    # Nearest expiry
    nearest = batches[batches["exp"].notna()].sort_values("exp").head(8)
    expiry_block = {"title": L("תפוגות קרובות", "Nearest expiry dates"), "table": None, "empty": None}
    if nearest.empty:
        expiry_block["empty"] = L("אין אצוות עם תאריך תפוגה.", "No batches with an expiry date.")
    else:
        expiry_block["table"] = _table(
            [L("מק\"ט", "SKU"), L("פריט", "Item"), L("אצווה", "Batch"), L("כמות", "Qty"), L("תפוגה", "Expiry")],
            [
                [
                    str(r.sku),
                    "?" if pd.isna(r.name) else str(r.name),
                    str(r.batch_no),
                    _format_qty(
                        float(r.weight_grams if r.item_type in ("RAW", "BULK") else r.qty_units),
                        r.item_type in ("RAW", "BULK"),
                        "יח'" if is_he else "u",
                        "גרם" if is_he else "g",
                    ),
                    _format_date(r.expiry_date, is_he),
                ]
                for r in nearest.itertuples()
            ],
        )

    # Open purchase orders
    po_block = {"title": L("הזמנות רכש פתוחות לפי ETA", "Open purchase orders by ETA"), "table": None, "empty": None}
    if pos.empty:
        po_block["empty"] = L("אין הזמנות רכש פתוחות.", "No open purchase orders.")
    else:
        po_block["table"] = _table(
            [L("מק\"ט", "SKU"), L("פריט", "Item"), L("הזמנה", "PO"), L("ספק", "Supplier"), "ETA", L("סטטוס", "Status")],
            [
                [
                    str(r.sku),
                    "?" if pd.isna(r.name) else str(r.name),
                    str(r.po_number),
                    str(r.supplier),
                    _format_date(r.eta_date, is_he),
                    str(r.status),
                ]
                for r in pos.itertuples()
            ],
        )

    return {
        "title": L("לוח בקרה", "Dashboard"),
        "subtitle": L(
            "סקירה כללית של המלאי, תאריכי התפוגה וההזמנות הפתוחות.",
            "Overview of stock levels, expiry dates, and open purchase orders.",
        ),
        "metrics": metrics,
        "blocks": [capacity_block, margin_block, expiry_block, po_block],
    }
