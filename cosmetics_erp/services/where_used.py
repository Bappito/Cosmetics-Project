"""'Where used' simulator: how each component's stock moves week by week.

Each component starts with its current stock. Arrivals from open purchase orders are added in
their ETA week, and every parent product that uses the component takes its weekly need. A cell
is short when the running balance goes below zero.

The web views only format the numbers this returns.
"""

from __future__ import annotations

from collections import defaultdict

WEEKS = ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"]
WEIGHT_TYPES = ("RAW", "BULK")
EPS = 1e-6


def _is_weight(comp_type: str) -> bool:
    return comp_type in WEIGHT_TYPES


def _per_unit(row: dict) -> float:
    """Amount of the component needed per one parent unit (grams for weight items, units otherwise)."""
    if _is_weight(row["comp_type"]):
        return float(row["req_weight_grams"] or 0.0)
    return float(row["req_qty_units"] or 0.0)


def _stock(row: dict) -> float:
    if _is_weight(row["comp_type"]):
        return float(row["avail_grams"] or 0.0)
    return float(row["avail_units"] or 0.0)


def compute_where_used(bom_rows: list[dict], incoming: dict) -> dict:
    """Week-by-week balance for every BOM row.

    bom_rows: dicts with component_sku, comp_type, req_qty_units, req_weight_grams,
        avail_units, avail_grams and W1..W8 (planned parent quantity for that week).
    incoming: {(sku, week): {"amt": base_units, "pos": [po_numbers]}} from InventoryService.get_incoming_map.

    Returns {"cells": [[cell per week] per row], "final": {component_sku: cell for W8 of its last row}}.
    Each cell holds before, used, after, is_ok, tot_used_all (all parents that week) and incoming.
    """
    running: dict[str, float] = {}
    for row in bom_rows:
        running.setdefault(row["component_sku"], _stock(row))

    weekly_total: dict[tuple[str, str], float] = defaultdict(float)
    for w in WEEKS:
        for row in bom_rows:
            weekly_total[(row["component_sku"], w)] += float(row[w] or 0.0) * _per_unit(row)

    cells: list[list[dict]] = [[] for _ in bom_rows]
    for w in WEEKS:
        arrivals_now: dict[str, dict] = {}
        for comp in list(running):
            ent = incoming.get((comp, w))
            if ent:
                running[comp] += ent["amt"]
                arrivals_now[comp] = ent

        for idx, row in enumerate(bom_rows):
            comp = row["component_sku"]
            used = float(row[w] or 0.0) * _per_unit(row)
            before = running.get(comp, 0.0)
            after = before - used
            running[comp] = after
            cells[idx].append({
                "week": w,
                "before": before,
                "used": used,
                "after": after,
                "is_ok": after >= -EPS,
                "tot_used_all": weekly_total[(comp, w)],
                "incoming": arrivals_now.get(comp),
            })

    final: dict[str, dict] = {}
    for idx, row in enumerate(bom_rows):
        final[row["component_sku"]] = cells[idx][-1]
    return {"cells": cells, "final": final}


def schedule_totals(schedule_rows: list[dict]) -> list[int]:
    """Planned total per parent SKU over the eight weeks."""
    return [int(sum(float(r[w] or 0) for w in WEEKS)) for r in schedule_rows]
