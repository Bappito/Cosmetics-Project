import pandas as pd
import pytest

from cosmetics_erp.services.costing import product_margins


def sample_catalog():
    return pd.DataFrame([
        {"sku": "R1", "name": "Raw", "item_type": "RAW", "item_price": 100.0, "qty_units": 0, "weight_grams": 0},
        {"sku": "B1", "name": "Bulk", "item_type": "BULK", "item_price": 0.0, "qty_units": 0, "weight_grams": 0},
        {"sku": "P1", "name": "Pack", "item_type": "PKG", "item_price": 2.0, "qty_units": 0, "weight_grams": 0},
        {"sku": "F1", "name": "Product", "item_type": "FG", "item_price": 20.0, "qty_units": 7, "weight_grams": 0},
    ])


def sample_bom():
    return pd.DataFrame([
        {"parent_sku": "B1", "component_sku": "R1", "req_qty_units": 0, "req_weight_grams": 1000.0},
        {"parent_sku": "F1", "component_sku": "B1", "req_qty_units": 0, "req_weight_grams": 50.0},
        {"parent_sku": "F1", "component_sku": "P1", "req_qty_units": 1.0, "req_weight_grams": 0.0},
    ])


def test_margin_uses_bulk_recipe_cost_and_packaging():
    row = product_margins(sample_catalog(), sample_bom()).set_index("sku").loc["F1"]
    # 50 g of bulk at 100 per kg = 5, plus one packaging unit at 2 = 7 cost
    assert row["cost"] == pytest.approx(7.0)
    assert row["margin"] == pytest.approx(13.0)
    assert row["margin_pct"] == pytest.approx(65.0)
    assert row["stock_margin"] == pytest.approx(13.0 * 7)


def test_product_without_bom_has_zero_cost_from_missing_components():
    empty_bom = pd.DataFrame(columns=["parent_sku", "component_sku", "req_qty_units", "req_weight_grams"])
    row = product_margins(sample_catalog(), empty_bom).set_index("sku").loc["F1"]
    assert row["cost"] == pytest.approx(20.0)
    assert row["margin"] == pytest.approx(0.0)
