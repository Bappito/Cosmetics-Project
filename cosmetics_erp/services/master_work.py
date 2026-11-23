"""Master work simulator: how many finished units can be made each week from the stock on hand.

Stock is used week by week. Packaging and bulk are consumed first, and a bulk shortfall is covered
by cooking more bulk from raw materials, if there is enough of them. Arrivals from open purchase
orders come in during their ETA week.
"""

from __future__ import annotations

import pandas as pd

from .where_used import WEEKS

EPS = 1e-6


def simulate_master_work(catalog: pd.DataFrame, bom: pd.DataFrame, fg_rows: list[dict], incoming: dict,
                         fmt_qty) -> dict:
    """Return {(fg_sku, week): cell}.

    catalog: sku, name, item_type, qty_units, weight_grams.
    bom: parent_sku, component_sku, comp_type, req_qty_units, req_weight_grams.
    fg_rows: dicts with sku and W1..W8 (planned finished units).
    fmt_qty(value, is_weight) formats a base-unit amount for display.

    A cell holds planned, makeable, missing_fg, is_ok, shortages and arrivals.
    """
    cat = catalog.set_index("sku")
    names = cat["name"].to_dict()
    kinds = cat["item_type"].to_dict()
    bom_by_parent = {p: g.to_dict("records") for p, g in bom.groupby("parent_sku")}

    rem_pkg = {s: float(r["qty_units"] or 0) for s, r in cat.iterrows() if r["item_type"] == "PKG"}
    rem_bulk = {s: float(r["weight_grams"] or 0) for s, r in cat.iterrows() if r["item_type"] == "BULK"}
    rem_raw = {s: float(r["weight_grams"] or 0) for s, r in cat.iterrows() if r["item_type"] == "RAW"}

    cells: dict[tuple[str, str], dict] = {}
    for w in WEEKS:
        arrived: dict[str, dict] = {}
        for stock in (rem_pkg, rem_bulk, rem_raw):
            for key in list(stock):
                ent = incoming.get((key, w))
                if ent:
                    stock[key] += ent["amt"]
                    arrived[key] = ent

        for fg in fg_rows:
            f_sku = fg["sku"]
            planned = int(fg[w] or 0)
            sub = bom_by_parent.get(f_sku, [])

            # Arrivals for the components of this product, and for the components of its bulks.
            related: list[str] = []
            for line in sub:
                related.append(line["component_sku"])
                if line["comp_type"] == "BULK":
                    related += [x["component_sku"] for x in bom_by_parent.get(line["component_sku"], [])]
            arrivals = []
            for s_key in dict.fromkeys(related):
                ent = arrived.get(s_key)
                if ent and s_key in names:
                    is_w = kinds[s_key] in ("RAW", "BULK")
                    arrivals.append({
                        "sku": s_key, "name": names[s_key], "amount": fmt_qty(ent["amt"], is_w),
                        "pos": list(ent["pos"]),
                    })

            shortages: list[dict] = []
            makeable = planned
            for line in sub:
                c_sku = line["component_sku"]
                if c_sku not in names:
                    continue
                c_name = names[c_sku]

                if line["comp_type"] == "PKG":
                    per_unit = float(line["req_qty_units"] or 0)
                    avail = rem_pkg.get(c_sku, 0.0)
                    can = int(max(0.0, avail) // per_unit) if per_unit > 0 else planned
                    makeable = min(makeable, can)
                    after = avail - planned * per_unit
                    rem_pkg[c_sku] = after
                    if after < -EPS:
                        shortages.append({"kind": "pkg", "sku": c_sku, "name": c_name, "after": after, "is_weight": False})

                elif line["comp_type"] == "BULK":
                    per_unit_g = float(line["req_weight_grams"] or 0)
                    need_g = planned * per_unit_g
                    avail_b = rem_bulk.get(c_sku, 0.0)
                    if avail_b >= need_g - EPS:
                        rem_bulk[c_sku] = avail_b - need_g
                        continue

                    # Not enough bulk: cook the rest from raw materials, as far as they go.
                    existing_g = max(0.0, avail_b)
                    extra_kg = (need_g - existing_g) / 1000.0
                    max_kg = extra_kg
                    raw_short: list[dict] = []
                    for rb in bom_by_parent.get(c_sku, []):
                        r_sku = rb["component_sku"]
                        if r_sku not in names:
                            continue
                        per_kg = float(rb["req_weight_grams"] or 0)
                        avail_r = rem_raw.get(r_sku, 0.0)
                        can_kg = (max(0.0, avail_r) / per_kg) if per_kg > 0 else extra_kg
                        max_kg = min(max_kg, can_kg)
                        after_r = avail_r - extra_kg * per_kg
                        rem_raw[r_sku] = after_r
                        if after_r < -EPS:
                            raw_short.append({"kind": "raw", "sku": r_sku, "name": names[r_sku], "after": after_r, "is_weight": True})

                    usable_g = existing_g + max_kg * 1000.0
                    can_by_bulk = int(usable_g // per_unit_g) if per_unit_g > 0 else planned
                    makeable = min(makeable, can_by_bulk)
                    after_b = avail_b - need_g
                    rem_bulk[c_sku] = after_b
                    shortages.append({"kind": "bulk", "sku": c_sku, "name": c_name, "after": after_b, "is_weight": True})
                    shortages.extend(raw_short)

            cells[(f_sku, w)] = {
                "planned": planned,
                "makeable": makeable,
                "missing": max(0, planned - makeable),
                "is_ok": not shortages,
                "shortages": shortages,
                "arrivals": arrivals,
            }
    return cells
