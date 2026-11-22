import pandas as pd

from cosmetics_erp.services.capacity import packable_units


def test_limiting_component_sets_packable_units():
    catalog = pd.DataFrame([
        {"sku": "B1", "name": "Bulk", "item_type": "BULK", "weight_grams": 1000.0, "qty_units": 0},
        {"sku": "P1", "name": "Bottle", "item_type": "PKG", "weight_grams": 0, "qty_units": 30},
        {"sku": "F1", "name": "Cream", "item_type": "FG", "weight_grams": 0, "qty_units": 0},
    ])
    bom = pd.DataFrame([
        {"parent_sku": "F1", "component_sku": "B1", "req_qty_units": 0, "req_weight_grams": 50.0},
        {"parent_sku": "F1", "component_sku": "P1", "req_qty_units": 1.0, "req_weight_grams": 0.0},
    ])
    row = packable_units(catalog, bom).iloc[0]
    # Bulk allows 1000 / 50 = 20 units, bottles allow 30 / 1 = 30, so bulk limits it.
    assert row["packable_units"] == 20
    assert row["limiting_component"].startswith("B1")


def test_product_without_bom_packs_zero():
    catalog = pd.DataFrame([{"sku": "F2", "name": "Empty", "item_type": "FG", "weight_grams": 0, "qty_units": 0}])
    empty = pd.DataFrame(columns=["parent_sku", "component_sku", "req_qty_units", "req_weight_grams"])
    assert packable_units(catalog, empty).iloc[0]["packable_units"] == 0
