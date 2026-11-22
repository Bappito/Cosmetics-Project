from __future__ import annotations

"""Material requirements planning (MRP) for the eight-week schedule.

Flow of material:
    FG (finished, per unit) -> consumes BULK (grams) and PKG (units)
    BULK (in-house, per kg) -> consumes RAW (grams)
    RAW and PKG are bought, so they get purchase suggestions.

Weekly quantities are in base units: grams for RAW and BULK, units for PKG and FG.
Schedule values are planned parent quantities: units for FG, kg for BULK.
"""

import math
from collections import defaultdict

import pandas as pd

WEEKS = [f"W{i}" for i in range(1, 9)]
WEIGHT_TYPES = ("RAW", "BULK")
BUYABLE_TYPES = ("RAW", "PKG")


def _planned(schedule: pd.DataFrame, sku: str) -> list[float]:
    row = schedule[schedule["parent_sku"] == sku]
    if row.empty:
        return [0.0] * len(WEEKS)
    return [float(row.iloc[0][w] or 0.0) for w in WEEKS]


def mrp_suggestions(
    catalog: pd.DataFrame,
    bom: pd.DataFrame,
    schedule: pd.DataFrame,
    open_pos: pd.DataFrame,
) -> pd.DataFrame:
    """Return one row per suggested purchase, with the week it is needed.

    catalog needs: sku, name, item_type, qty_units, weight_grams, min_order_qty, main_supplier
    bom needs: parent_sku, component_sku, req_qty_units, req_weight_grams
    schedule needs: parent_sku, W1..W8 (planned quantities)
    open_pos needs: sku, qty_base, week (W1..W8 or None)
    """
    info = catalog.set_index("sku")
    types = info["item_type"].to_dict()
    stock = {
        sku: float(row["weight_grams"] if row["item_type"] in WEIGHT_TYPES else row["qty_units"] or 0.0)
        for sku, row in info.iterrows()
    }
    bom_by_parent = {parent: rows for parent, rows in bom.groupby("parent_sku")}

    # 1. Work out what FG and BULK need, week by week.
    bulk_demand_g = defaultdict(lambda: [0.0] * len(WEEKS))
    pkg_gross = defaultdict(lambda: [0.0] * len(WEEKS))
    for fg_sku in info.index[info["item_type"] == "FG"]:
        planned = _planned(schedule, fg_sku)
        for row in (bom_by_parent[fg_sku].itertuples() if fg_sku in bom_by_parent else []):
            comp_type = types.get(row.component_sku)
            for i, units in enumerate(planned):
                if comp_type == "BULK":
                    bulk_demand_g[row.component_sku][i] += units * float(row.req_weight_grams)
                elif comp_type == "PKG":
                    pkg_gross[row.component_sku][i] += units * float(row.req_qty_units)

    # 2. Bulk is made in-house: planned production plus any shortfall, in kg.
    raw_gross = defaultdict(lambda: [0.0] * len(WEEKS))
    for bulk_sku in info.index[info["item_type"] == "BULK"]:
        planned_kg = _planned(schedule, bulk_sku)
        balance = stock.get(bulk_sku, 0.0)
        production_g = [0.0] * len(WEEKS)
        for i in range(len(WEEKS)):
            supply = planned_kg[i] * 1000.0
            balance += supply
            balance -= bulk_demand_g[bulk_sku][i]
            extra = max(0.0, -balance)
            balance += extra
            production_g[i] = supply + extra
        for row in (bom_by_parent[bulk_sku].itertuples() if bulk_sku in bom_by_parent else []):
            if types.get(row.component_sku) == "RAW":
                for i in range(len(WEEKS)):
                    # BOM is grams per kg of bulk.
                    raw_gross[row.component_sku][i] += production_g[i] / 1000.0 * float(row.req_weight_grams)

    # 3. Buyable items: balance by week, suggest a purchase when it would go negative.
    gross = defaultdict(lambda: [0.0] * len(WEEKS))
    for sku, values in raw_gross.items():
        gross[sku] = [a + b for a, b in zip(gross[sku], values)]
    for sku, values in pkg_gross.items():
        gross[sku] = [a + b for a, b in zip(gross[sku], values)]

    arrivals = defaultdict(lambda: [0.0] * len(WEEKS))
    for row in open_pos.itertuples():
        if row.week in WEEKS:
            arrivals[row.sku][WEEKS.index(row.week)] += float(row.qty_base or 0.0)

    suggestions = []
    for sku in sorted(gross):
        if types.get(sku) not in BUYABLE_TYPES:
            continue
        moq_units = float(info.loc[sku, "min_order_qty"] or 0.0) if sku in info.index else 0.0
        moq = moq_units * 1000.0 if types.get(sku) == "RAW" else moq_units
        balance = stock.get(sku, 0.0)
        for i in range(len(WEEKS)):
            balance += arrivals[sku][i]
            balance -= gross[sku][i]
            if balance < 0:
                shortfall = -balance
                qty = math.ceil(shortfall / moq) * moq if moq > 0 else shortfall
                balance += qty
                suggestions.append({
                    "sku": sku,
                    "name": info.loc[sku, "name"],
                    "item_type": types.get(sku),
                    "need_week": WEEKS[i],
                    "shortfall_base": round(shortfall, 3),
                    "order_base": round(qty, 3),
                    "supplier": info.loc[sku, "main_supplier"] or "",
                })
    return pd.DataFrame(suggestions, columns=[
        "sku", "name", "item_type", "need_week", "shortfall_base", "order_base", "supplier",
    ])
