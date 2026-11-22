import pandas as pd

from cosmetics_erp.services.mrp import mrp_suggestions

WEEK_COLS = [f"W{i}" for i in range(1, 9)]


def catalog():
    return pd.DataFrame([
        {"sku": "R1", "name": "Oil", "item_type": "RAW", "qty_units": 0.0, "weight_grams": 500.0,
         "min_order_qty": 2.0, "main_supplier": "Acme"},
        {"sku": "B1", "name": "Bulk", "item_type": "BULK", "qty_units": 0.0, "weight_grams": 0.0,
         "min_order_qty": 0.0, "main_supplier": ""},
        {"sku": "P1", "name": "Bottle", "item_type": "PKG", "qty_units": 100.0, "weight_grams": 0.0,
         "min_order_qty": 50.0, "main_supplier": "Pack"},
        {"sku": "F1", "name": "Cream", "item_type": "FG", "qty_units": 0.0, "weight_grams": 0.0,
         "min_order_qty": 0.0, "main_supplier": ""},
    ])


def bom():
    return pd.DataFrame([
        {"parent_sku": "B1", "component_sku": "R1", "req_qty_units": 0.0, "req_weight_grams": 1000.0},
        {"parent_sku": "F1", "component_sku": "B1", "req_qty_units": 0.0, "req_weight_grams": 50.0},
        {"parent_sku": "F1", "component_sku": "P1", "req_qty_units": 1.0, "req_weight_grams": 0.0},
    ])


def schedule(fg_units_w1=0.0, fg_units_w2=0.0):
    row = {"parent_sku": "F1", **{w: 0.0 for w in WEEK_COLS}}
    row["W1"] = fg_units_w1
    row["W2"] = fg_units_w2
    bulk = {"parent_sku": "B1", **{w: 0.0 for w in WEEK_COLS}}
    return pd.DataFrame([row, bulk])


NO_POS = pd.DataFrame(columns=["sku", "qty_base", "week"])


def test_no_demand_means_no_suggestions():
    result = mrp_suggestions(catalog(), bom(), schedule(), NO_POS)
    assert result.empty


def test_packaging_shortfall_is_rounded_to_moq():
    # 200 units planned in W1 need 200 bottles; 100 in stock, so 100 short; MOQ 50 keeps 100.
    result = mrp_suggestions(catalog(), bom(), schedule(fg_units_w1=200.0), NO_POS)
    pkg = result[result["sku"] == "P1"].iloc[0]
    assert pkg["need_week"] == "W1"
    assert pkg["shortfall_base"] == 100.0
    assert pkg["order_base"] == 100.0


def test_raw_material_follows_bulk_production_in_grams():
    # 200 units x 50 g bulk = 10 000 g bulk. Stock is 0, so 10 kg of bulk is produced,
    # which needs 10 kg of RAW at 1000 g per kg of bulk = 10 000 g, minus 500 g in stock.
    result = mrp_suggestions(catalog(), bom(), schedule(fg_units_w1=200.0), NO_POS)
    raw = result[result["sku"] == "R1"].iloc[0]
    assert raw["need_week"] == "W1"
    assert raw["shortfall_base"] == 9500.0
    # MOQ is 2 kg = 2000 g, so the order rounds up to 10 000 g.
    assert raw["order_base"] == 10000.0
    assert raw["supplier"] == "Acme"


def test_open_purchase_order_covers_the_need():
    pos = pd.DataFrame([{"sku": "P1", "qty_base": 500.0, "week": "W1"}])
    result = mrp_suggestions(catalog(), bom(), schedule(fg_units_w1=200.0), pos)
    assert result[result["sku"] == "P1"].empty


def test_later_week_need_is_reported_for_that_week():
    result = mrp_suggestions(catalog(), bom(), schedule(fg_units_w2=200.0), NO_POS)
    pkg = result[result["sku"] == "P1"].iloc[0]
    assert pkg["need_week"] == "W2"
