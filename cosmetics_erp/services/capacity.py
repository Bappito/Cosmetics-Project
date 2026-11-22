from __future__ import annotations

import math

import pandas as pd


def packable_units(catalog: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    """How many finished units can be packed from current stock, and which component limits it.

    Uses current catalog balances (BULK in grams, PKG in units). Components with a zero
    requirement are ignored. A product with no BOM rows reports zero units.
    """
    types = catalog.set_index("sku")["item_type"].to_dict()
    names = catalog.set_index("sku")["name"].fillna("").to_dict()
    balance_grams = catalog.set_index("sku")["weight_grams"].fillna(0.0).astype(float).to_dict()
    balance_units = catalog.set_index("sku")["qty_units"].fillna(0.0).astype(float).to_dict()
    fg_skus = catalog.loc[catalog["item_type"] == "FG", "sku"].tolist()

    rows = []
    for sku in fg_skus:
        requirements = bom[bom["parent_sku"] == sku]
        best_units = None
        limiting = "-"
        for req in requirements.itertuples():
            comp_type = types.get(req.component_sku)
            if comp_type == "BULK":
                need = float(req.req_weight_grams)
                have = balance_grams.get(req.component_sku, 0.0)
            elif comp_type == "PKG":
                need = float(req.req_qty_units)
                have = balance_units.get(req.component_sku, 0.0)
            else:
                continue
            if need <= 0:
                continue
            possible = math.floor(have / need + 1e-9)
            if best_units is None or possible < best_units:
                best_units = possible
                limiting = f"{req.component_sku} - {names.get(req.component_sku, '')}"
        rows.append({
            "sku": sku,
            "name": names.get(sku, ""),
            "packable_units": int(best_units) if best_units is not None else 0,
            "limiting_component": limiting if best_units is not None else "-",
        })
    return pd.DataFrame(rows, columns=["sku", "name", "packable_units", "limiting_component"])
