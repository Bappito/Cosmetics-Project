import pytest

from cosmetics_erp.services.erp_import import build_po_rows, build_stock_rows, guess_column, read_table

KNOWN = {"1001", "3001"}
WEIGHT = {"1001"}


def test_sap_style_stock_sums_duplicates_and_converts_kg():
    df = read_table("stock.csv", b"MATNR,CHARG,LABST\n1001,B1,10\n1001,B2,5\n3001,,400\n")
    rows, errors = build_stock_rows(df, {"sku": "MATNR", "qty": "LABST"}, KNOWN, WEIGHT, 1000.0)
    got = dict(zip(rows["sku"], rows["counted"]))
    assert got == {"1001": 15000.0, "3001": 400.0}
    assert errors == []


def test_unknown_sku_and_bad_quantity_are_reported():
    df = read_table("stock.csv", b"MATNR,LABST\n9999,1\n1001,abc\n")
    rows, errors = build_stock_rows(df, {"sku": "MATNR", "qty": "LABST"}, KNOWN, WEIGHT, 1000.0)
    assert rows.empty
    assert any("9999" in e for e in errors)
    assert len(errors) == 2


def test_priority_style_po_parses_dates_and_units():
    df = read_table("po.csv", b"PO#,PARTNAME,QTY,SUPNAME,DUEDATE\nPO-900,1001,2,Acme,25/12/2026\nPO-901,3001,600,Pack,01/01/2027\n")
    mapping = {"sku": "PARTNAME", "qty": "QTY", "po_number": "PO#", "supplier": "SUPNAME", "eta": "DUEDATE"}
    rows, errors = build_po_rows(df, mapping, KNOWN, WEIGHT, 1000.0)
    assert errors == []
    by_po = {r["po_number"]: r for r in rows}
    assert by_po["PO-900"]["qty_base"] == 2000.0
    assert by_po["PO-900"]["eta"] == "2026-12-25"
    assert by_po["PO-901"]["qty_base"] == 600.0


def test_guess_column_matches_known_headers():
    assert guess_column(["MATNR", "LABST"], "sku") == "MATNR"
    assert guess_column(["foo"], "sku") is None


def test_unsupported_file_type_raises():
    with pytest.raises(ValueError):
        read_table("data.pdf", b"%PDF")
