"""Builds the dashboard figures from the existing services. No Django or Streamlit imports."""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from cosmetics_erp.services.capacity import packable_units
from cosmetics_erp.services.costing import product_margins
from cosmetics_erp.services.planning import get_plan_start

EXPIRY_WARNING_DAYS = 30


def _parse_date(value):
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except (TypeError, ValueError):
        return None


def _fmt_date(value, is_he: bool) -> str:
    d = _parse_date(value)
    if d is None:
        return "—"
    return d.strftime("%d/%m/%Y") if is_he else d.strftime("%b %d, %Y")


def _fmt_amount(value: float, is_weight: bool, words: dict) -> str:
    if is_weight:
        return f"{value / 1000:,.2f} {words['kg']}"
    return f"{value:,.0f} {words['units']}"


def build_dashboard(conn, is_he: bool, words: dict, include_profit: bool = True) -> dict:
    """Return everything the dashboard template shows."""
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

    today = date.today()
    soon = today + timedelta(days=EXPIRY_WARNING_DAYS)
    batches["exp"] = batches["expiry_date"].map(_parse_date)
    expired = int((batches["exp"].notna() & (batches["exp"] < today)).sum())
    expiring = int((batches["exp"].notna() & (batches["exp"] >= today) & (batches["exp"] <= soon)).sum())

    capacity = [
        {
            "sku": r.sku,
            "name": r.name or "",
            "packable": int(r.packable_units),
            "limiting": r.limiting_component,
        }
        for r in packable_units(cat, bom).itertuples()
    ]

    margins = [] if not include_profit else [
        {
            "sku": r.sku,
            "name": r.name or "",
            "price": f"₪{r.price:,.2f}",
            "cost": f"₪{r.cost:,.2f}",
            "margin": f"₪{r.margin:,.2f}",
            "margin_pct": "—" if pd.isna(r.margin_pct) else f"{r.margin_pct:,.1f}%",
            "stock_units": f"{r.stock_units:,.0f}",
            "stock_margin": f"₪{r.stock_margin:,.0f}",
        }
        for r in product_margins(cat, bom).itertuples()
    ]

    is_weight = batches["item_type"].isin(["RAW", "BULK"])
    nearest = batches[batches["exp"].notna()].sort_values("exp").head(8)
    expiry_rows = [
        {
            "sku": r.sku,
            "name": r.name or "?",
            "batch": r.batch_no,
            "qty": _fmt_amount(float(r.weight_grams if w else r.qty_units), w, words),
            "expiry": _fmt_date(r.expiry_date, is_he),
        }
        for r, w in zip(nearest.itertuples(), is_weight.loc[nearest.index])
    ]

    po_rows = [
        {
            "sku": r.sku,
            "name": r.name or "?",
            "po": r.po_number,
            "supplier": r.supplier or "",
            "eta": _fmt_date(r.eta_date, is_he),
            "status": r.status,
        }
        for r in pos.itertuples()
    ]

    return {
        "plan_start": get_plan_start(conn),
        "open_pos": len(pos),
        "expiring": expiring,
        "expired": expired,
        "capacity": capacity,
        "margins": margins,
        "expiry_rows": expiry_rows,
        "po_rows": po_rows,
    }
