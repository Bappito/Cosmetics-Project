from cosmetics_erp.services.bom import to_bom_rows, validate_bom

TYPES = {"R1": "RAW", "B1": "BULK", "P1": "PKG", "F1": "FG", "F2": "FG"}


def test_valid_bulk_tree_passes():
    rows = [{"component_sku": "R1", "quantity": 700}]
    assert validate_bom("B2", "BULK", rows, TYPES) == []


def test_valid_fg_tree_passes():
    rows = [{"component_sku": "B1", "quantity": 50}, {"component_sku": "P1", "quantity": 1}]
    assert validate_bom("F2", "FG", rows, TYPES) == []


def test_bulk_cannot_contain_packaging():
    rows = [{"component_sku": "P1", "quantity": 1}]
    errors = validate_bom("B2", "BULK", rows, TYPES)
    assert any("PKG" in e for e in errors)


def test_fg_cannot_contain_raw_material():
    rows = [{"component_sku": "R1", "quantity": 10}]
    assert validate_bom("F2", "FG", rows, TYPES)


def test_duplicate_and_self_and_unknown_are_reported():
    rows = [
        {"component_sku": "P1", "quantity": 1},
        {"component_sku": "P1", "quantity": 2},
        {"component_sku": "F2", "quantity": 1},
        {"component_sku": "9999", "quantity": 1},
    ]
    errors = validate_bom("F2", "FG", rows, TYPES)
    assert any("מופיע פעמיים" in e for e in errors)
    assert any("את עצמו" in e for e in errors)
    assert any("9999" in e for e in errors)


def test_quantity_must_be_positive():
    rows = [{"component_sku": "P1", "quantity": 0}]
    assert validate_bom("F2", "FG", rows, TYPES)


def test_empty_tree_is_rejected():
    assert validate_bom("F2", "FG", [], TYPES)


def test_rows_store_quantity_in_the_right_column():
    rows = [{"component_sku": "B1", "quantity": 50}, {"component_sku": "P1", "quantity": 1}]
    stored = to_bom_rows("F2", rows, TYPES, "FG")
    assert stored[0] == ("F2", "B1", "BULK", 0.0, 50.0)
    assert stored[1] == ("F2", "P1", "PKG", 1.0, 0.0)
