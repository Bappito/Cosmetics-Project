from datetime import date, timedelta

from cosmetics_erp.services.inventory import InventoryService
from cosmetics_erp.services.manufacturing import expiry_cap, plan_components, post_run
from cosmetics_erp.services.planning import PlanningService


def make_service(conn):
    planning = PlanningService(periods=[], translate=lambda he, en: en)
    return InventoryService(conn, lambda he, en: en, planning.parse_date, planning.eta_to_week)


def bulk_components(conn, parent, kg):
    rows = conn.execute("SELECT component_sku, req_weight_grams FROM BOM WHERE parent_sku = ?", (parent,)).fetchall()
    return [{"sku": sku, "need": grams * kg, "is_weight": True, "from_wh": "WH_RAW"} for sku, grams in rows]


def test_production_consumes_components_and_creates_bulk_batch(conn):
    svc = make_service(conn)
    before_1004 = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='1004'").fetchone()[0]
    before_bulk = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='2001'").fetchone()[0]
    plans, shortages = plan_components(svc, bulk_components(conn, "2001", 2.0))
    assert shortages == []
    result = post_run(conn, svc, kind="production", parent_sku="2001", batch_no="TEST-BULK-1", plans=plans,
                      expiry=(date.today() + timedelta(days=180)).isoformat(), output_amount=2000.0,
                      output_is_weight=True, now_d=date.today().isoformat(), kg_display=2.0)
    # 700 g per kg of the 1004 component, for 2 kg
    after_1004 = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='1004'").fetchone()[0]
    assert abs((before_1004 - after_1004) - 1400.0) < 1e-6
    after_bulk = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='2001'").fetchone()[0]
    assert abs((after_bulk - before_bulk) - 2000.0) < 1e-6
    batch = conn.execute("SELECT weight_grams, source FROM Batches WHERE batch_no='TEST-BULK-1'").fetchone()
    assert batch == (2000.0, "PRODUCTION")
    assert result["capped"] is False


def test_expiry_is_capped_at_earliest_component_expiry(conn):
    svc = make_service(conn)
    plans, _ = plan_components(svc, bulk_components(conn, "2001", 1.0))
    earliest = min(p["expiry"] for plan in plans for p in plan["picks"] if p["expiry"])
    far_future = "2099-01-01"
    exp, capped, limiting = expiry_cap(plans, far_future)
    assert capped is True
    assert exp == earliest == limiting


def test_shortage_is_reported_per_component(conn):
    svc = make_service(conn)
    plans, shortages = plan_components(svc, bulk_components(conn, "2001", 100.0))  # far more than stock
    assert shortages
    assert all(s["short"] > 0 for s in shortages)


def test_packaging_consumes_bulk_and_packaging_and_creates_finished_batch(conn):
    svc = make_service(conn)
    bulk_before = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='2001'").fetchone()[0]
    bottle_before = conn.execute("SELECT qty_units FROM Catalog WHERE sku='3001'").fetchone()[0]
    components = [
        {"sku": "2001", "need": 50.0 * 10, "is_weight": True, "from_wh": "WH_BULK"},
        {"sku": "3001", "need": 1.0 * 10, "is_weight": False, "from_wh": "WH_PACK"},
    ]
    plans, shortages = plan_components(svc, components)
    assert shortages == []
    post_run(conn, svc, kind="packaging", parent_sku="5001", batch_no="TEST-FG-1", plans=plans,
             expiry=(date.today() + timedelta(days=700)).isoformat(), output_amount=10.0,
             output_is_weight=False, now_d=date.today().isoformat())
    assert abs(conn.execute("SELECT weight_grams FROM Catalog WHERE sku='2001'").fetchone()[0] - (bulk_before - 500)) < 1e-6
    assert conn.execute("SELECT qty_units FROM Catalog WHERE sku='3001'").fetchone()[0] == bottle_before - 10
    fg = conn.execute("SELECT qty_units, source FROM Batches WHERE batch_no='TEST-FG-1'").fetchone()
    assert fg == (10.0, "PACKING")
