"""Personal what-if scenarios: a list of planned finished-product orders by week.

A scenario is run against today's real stock and open purchase orders, using the same MRP
rules as the purchase planning screen. Nothing is written to the ERP data.
"""
from __future__ import annotations

import pandas as pd

from cosmetics_erp.services.mrp import WEEKS, mrp_suggestions

SCHEDULE_COLUMNS = ["parent_sku", *WEEKS]


def scenario_schedule(lines: list[dict]) -> pd.DataFrame:
    """lines: dicts with sku, week (1..8) and qty (in the product's base unit).

    Returns the schedule in the shape mrp_suggestions expects (one row per product, W1..W8).
    """
    per_sku: dict[str, list[float]] = {}
    for line in lines:
        week = int(line["week"])
        if not 1 <= week <= len(WEEKS):
            continue
        values = per_sku.setdefault(str(line["sku"]), [0.0] * len(WEEKS))
        values[week - 1] += float(line["qty"])
    rows = [{"parent_sku": sku, **{w: vals[i] for i, w in enumerate(WEEKS)}} for sku, vals in per_sku.items()]
    return pd.DataFrame(rows, columns=SCHEDULE_COLUMNS)


def scenario_shortages(catalog: pd.DataFrame, bom: pd.DataFrame, open_pos: pd.DataFrame, lines: list[dict]) -> pd.DataFrame:
    """Shortages and suggested purchases for the scenario, week by week."""
    return mrp_suggestions(catalog, bom, scenario_schedule(lines), open_pos)
