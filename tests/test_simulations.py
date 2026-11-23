import pandas as pd
import pytest

from cosmetics_erp.services.master_work import simulate_master_work
from cosmetics_erp.services.quick_command import CommandError, added_base_amount, check_unit_for_type, parse_command
from cosmetics_erp.services.where_used import WEEKS, compute_where_used

WEEKLY = {w: 0 for w in WEEKS}


def bom_row(component, comp_type, parent, per_unit, stock, **weeks):
    row = {
        "component_sku": component, "comp_type": comp_type, "parent_sku": parent,
        "req_qty_units": per_unit if comp_type == "PKG" else 0.0,
        "req_weight_grams": per_unit if comp_type != "PKG" else 0.0,
        "avail_units": stock if comp_type == "PKG" else 0.0,
        "avail_grams": stock if comp_type != "PKG" else 0.0,
    }
    row.update(WEEKLY)
    row.update(weeks)
    return row


def test_parse_command_reads_amount_unit_and_sku():
    assert parse_command("add 5 kg to 1001") == {"sku": "1001", "amount": 5.0, "unit": "kg"}
    assert parse_command("תוסיף 300 יחידות ל-3001") == {"sku": "3001", "amount": 300.0, "unit": "units"}
    assert added_base_amount(2.5, "kg") == 2500.0


@pytest.mark.parametrize("text, key", [
    ("add 5 to 1001", None),  # handled below: needs unit check, not a parse error
    ("add 0 kg to 1001", "not_positive"),
    ("kg 1001", "need_two_numbers"),
])
def test_parse_command_errors(text, key):
    if key is None:
        assert parse_command(text)["unit"] is None
        with pytest.raises(CommandError) as exc:
            check_unit_for_type("RAW", None, 5)
        assert exc.value.key == "weight_needs_unit"
    else:
        with pytest.raises(CommandError) as exc:
            parse_command(text)
        assert exc.value.key == key


def test_units_must_be_whole_for_unit_items():
    with pytest.raises(CommandError) as exc:
        check_unit_for_type("FG", "units", 2.5)
    assert exc.value.key == "unit_whole_numbers"


def test_where_used_balance_moves_with_use_and_arrivals():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=30, stock=100, W1=1, W3=2)]
    incoming = {("PK1", "W2"): {"amt": 50.0, "pos": ["PO-1"]}}
    result = compute_where_used(rows, incoming)
    cells = result["cells"][0]
    assert cells[0]["after"] == 70            # 100 - 30
    # Arrivals are counted before the week's use, as in the original simulator.
    assert cells[1]["before"] == 120          # 70 + 50 arrives in W2
    assert cells[1]["incoming"]["pos"] == ["PO-1"]
    assert cells[1]["after"] == 120           # no use in W2
    assert cells[2]["used"] == 60             # 2 units x 30
    assert cells[2]["is_ok"] is True
    assert result["final"]["PK1"]["after"] == 60


def test_where_used_flags_a_shortage():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=30, stock=50, W4=3)]
    cell = compute_where_used(rows, {})["cells"][0][3]
    assert cell["after"] == -40
    assert cell["is_ok"] is False


def test_master_work_limited_by_packaging_stock():
    catalog = pd.DataFrame([
        {"sku": "F1", "name": "Product", "item_type": "FG", "qty_units": 0, "weight_grams": 0},
        {"sku": "P1", "name": "Bottle", "item_type": "PKG", "qty_units": 25, "weight_grams": 0},
    ])
    bom = pd.DataFrame([{"parent_sku": "F1", "component_sku": "P1", "comp_type": "PKG",
                         "req_qty_units": 10, "req_weight_grams": 0}])
    fg = [{"sku": "F1", **dict(WEEKLY, W1=3, W2=0)}]
    cells = simulate_master_work(catalog, bom, fg, {}, lambda v, is_w: f"{v:g}")
    week1 = cells[("F1", "W1")]
    assert week1["planned"] == 3
    assert week1["makeable"] == 2             # 25 bottles hold 2 full units of 10
    assert week1["missing"] == 1
    assert week1["is_ok"] is False
    assert week1["shortages"][0]["sku"] == "P1"
    # The packaging balance went negative in W1 and carries forward, so W2 stays short too.
    assert cells[("F1", "W2")]["is_ok"] is False
    assert cells[("F1", "W2")]["shortages"][0]["sku"] == "P1"


from cosmetics_erp.services.where_used import COVERED, IDLE, READY, SHORT, readiness


def test_readiness_green_when_stock_alone_covers_the_need():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=10, stock=100, W1=2)]
    cell = readiness(rows, {})["cells"][0][0]
    assert cell["status"] == READY


def test_readiness_yellow_only_when_the_arrival_gets_there_in_time():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=10, stock=10, W2=2)]  # needs 20, has 10
    incoming = {("PK1", "W2"): {"amt": 15.0, "pos": ["PO-9"]}}          # arrives in the same week
    cells = readiness(rows, incoming)["cells"][0]
    assert cells[1]["status"] == COVERED
    assert cells[0]["status"] == IDLE


def test_readiness_red_even_with_every_arrival():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=10, stock=10, W2=5)]  # needs 50, has 10
    incoming = {("PK1", "W2"): {"amt": 15.0, "pos": ["PO-9"]}}
    assert readiness(rows, incoming)["cells"][0][1]["status"] == SHORT


def test_readiness_arrival_after_the_need_does_not_help():
    rows = [bom_row("PK1", "PKG", "F1", per_unit=10, stock=10, W1=2)]  # needs 20 in W1
    incoming = {("PK1", "W2"): {"amt": 50.0, "pos": ["PO-9"]}}          # lands only in W2
    assert readiness(rows, incoming)["cells"][0][0]["status"] == SHORT
