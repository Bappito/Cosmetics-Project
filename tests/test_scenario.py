import pandas as pd

from cosmetics_erp.services.mrp import WEEKS
from cosmetics_erp.services.scenario import scenario_schedule, scenario_shortages


def test_schedule_adds_quantities_per_week_and_product():
    lines = [
        {"sku": "5001", "week": 2, "qty": 100},
        {"sku": "5001", "week": 2, "qty": 50},
        {"sku": "5002", "week": 8, "qty": 10},
    ]
    schedule = scenario_schedule(lines)
    five = schedule[schedule["parent_sku"] == "5001"].iloc[0]
    assert five["W2"] == 150
    assert five["W1"] == 0
    assert list(schedule.columns) == ["parent_sku", *WEEKS]


def test_week_outside_the_plan_is_ignored():
    schedule = scenario_schedule([{"sku": "5001", "week": 9, "qty": 10}])
    assert schedule.empty


def test_scenario_with_no_bom_creates_no_shortage():
    catalog = pd.DataFrame(columns=["sku", "name", "item_type", "qty_units", "weight_grams",
                                    "min_order_qty", "main_supplier"])
    bom = pd.DataFrame(columns=["parent_sku", "component_sku", "req_qty_units", "req_weight_grams"])
    open_pos = pd.DataFrame(columns=["sku", "qty_base", "week"])
    result = scenario_shortages(catalog, bom, open_pos, [{"sku": "5001", "week": 1, "qty": 10}])
    assert result.empty
