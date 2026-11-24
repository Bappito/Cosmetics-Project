"""Stock summary: totals per warehouse and per item type, read from the catalog balances."""
from __future__ import annotations

import pandas as pd
from django.contrib.auth.decorators import login_required

from .page import Page


@login_required
def stock_summary(request):
    with Page(request, "stock_summary") as page:
        L = page.L
        df = pd.read_sql(
            "SELECT sku, item_type, primary_warehouse, qty_units, weight_grams FROM Catalog",
            page.conn,
        )
        df["primary_warehouse"] = df["primary_warehouse"].fillna("—").replace("", "—")
        df["item_type"] = df["item_type"].fillna("—")
        df["has_stock"] = (df["qty_units"].fillna(0) > 0) | (df["weight_grams"].fillna(0) > 0)

        def summarize(column: str, label: str) -> list[dict]:
            grouped = df.groupby(column).agg(
                skus=("sku", "count"),
                in_stock=("has_stock", "sum"),
                units=("qty_units", "sum"),
                grams=("weight_grams", "sum"),
            ).reset_index()
            return [
                {
                    label: r[column],
                    "skus": int(r["skus"]),
                    "in_stock": int(r["in_stock"]),
                    "units": f"{float(r['units']):,.0f}",
                    "kg": f"{float(r['grams']) / 1000:,.2f}",
                }
                for _, r in grouped.iterrows()
            ]

        recon = pd.read_sql(
            "SELECT c.sku, c.name, c.item_type, c.qty_units, c.weight_grams, "
            "COALESCE(SUM(b.qty_units), 0) AS batch_units, COALESCE(SUM(b.weight_grams), 0) AS batch_grams "
            "FROM Catalog c LEFT JOIN Batches b ON b.sku = c.sku AND b.status = 'Active' GROUP BY c.sku",
            page.conn,
        )
        mismatches = []
        for r in recon.itertuples():
            is_w = r.item_type in ("RAW", "BULK")
            catalog_value = float((r.weight_grams if is_w else r.qty_units) or 0)
            batch_value = float((r.batch_grams if is_w else r.batch_units) or 0)
            if abs(catalog_value - batch_value) > 0.001:
                mismatches.append({
                    "sku": r.sku, "name": r.name or "?", "type": r.item_type,
                    "catalog": page.fmt(catalog_value, is_w), "batches": page.fmt(batch_value, is_w),
                    "diff": page.fmt(catalog_value - batch_value, is_w),
                })

        return page.render(
            "erp/stock_summary.html",
            mismatches=mismatches,
            title=L("סיכום מלאי", "Stock summary"),
            subtitle=L("סך המלאי לפי מחסן וסוג פריט, מתוך יתרות הקטלוג.",
                       "Total stock by warehouse and item type, from the catalog balances."),
            metrics=[
                {"label": L("מקטים בקטלוג", "SKUs in catalog"), "value": f"{len(df):,}"},
                {"label": L("מקטים עם מלאי", "SKUs with stock"), "value": f"{int(df['has_stock'].sum()):,}"},
                {"label": L("סה\"כ יחידות", "Total units"), "value": f"{float(df['qty_units'].fillna(0).sum()):,.0f}"},
                {"label": L("סה\"כ ק\"ג (משקל)", "Total kg (weight)"), "value": f"{float(df['weight_grams'].fillna(0).sum()) / 1000:,.1f}"},
            ],
            by_warehouse=summarize("primary_warehouse", "warehouse"),
            by_type=summarize("item_type", "type"),
            wh_label=L("מחסן", "Warehouse"),
            type_label=L("סוג פריט", "Item type"),
        )
