from __future__ import annotations

import pandas as pd

# Price conventions in the catalog:
#   RAW and BULK item_price is per kilogram; BOM weights are in grams.
#   PKG and FG item_price is per unit.
# A BULK's cost is built from its own BOM, so it reflects the current recipe cost.
# FG item_price is treated as the selling price per unit.

_WEIGHT_TYPES = ("RAW", "BULK")


def product_margins(catalog: pd.DataFrame, bom: pd.DataFrame) -> pd.DataFrame:
    """Return cost, price and margin for every FG product.

    catalog needs: sku, name, item_type, item_price, qty_units
    bom needs: parent_sku, component_sku, req_qty_units, req_weight_grams
    """
    types = catalog.set_index("sku")["item_type"].to_dict()
    prices = catalog.set_index("sku")["item_price"].fillna(0.0).astype(float).to_dict()
    children = {parent: rows for parent, rows in bom.groupby("parent_sku")}
    kg_cost_cache: dict[str, float] = {}

    def cost_per_kg(sku: str, depth: int = 0) -> float:
        """Cost of one kilogram of a RAW or BULK item."""
        if sku in kg_cost_cache:
            return kg_cost_cache[sku]
        if types.get(sku) == "RAW" or sku not in children or depth > 5:
            cost = prices.get(sku, 0.0)
        else:
            cost = 0.0
            for row in children[sku].itertuples():
                cost += float(row.req_weight_grams) / 1000.0 * cost_per_kg(row.component_sku, depth + 1)
        kg_cost_cache[sku] = cost
        return cost

    def unit_cost(sku: str, depth: int = 0) -> float:
        """Cost of one unit of an FG or PKG item."""
        if sku not in children or depth > 5:
            return prices.get(sku, 0.0)
        cost = 0.0
        for row in children[sku].itertuples():
            comp_type = types.get(row.component_sku)
            if comp_type in _WEIGHT_TYPES:
                cost += float(row.req_weight_grams) / 1000.0 * cost_per_kg(row.component_sku)
            else:
                cost += float(row.req_qty_units) * unit_cost(row.component_sku, depth + 1)
        return cost

    fg = catalog[catalog["item_type"] == "FG"].copy()
    fg["price"] = fg["item_price"].fillna(0.0).astype(float)
    fg["cost"] = [unit_cost(sku) for sku in fg["sku"]]
    fg["margin"] = fg["price"] - fg["cost"]
    fg["margin_pct"] = (fg["margin"] / fg["price"].where(fg["price"] > 0)) * 100.0
    fg["stock_units"] = fg["qty_units"].fillna(0.0).astype(float)
    fg["stock_margin"] = fg["margin"] * fg["stock_units"]
    return fg[["sku", "name", "price", "cost", "margin", "margin_pct", "stock_units", "stock_margin"]].reset_index(drop=True)
