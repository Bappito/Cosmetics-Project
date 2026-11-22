from datetime import date, timedelta

from cosmetics_erp.services.inventory import InventoryService
from cosmetics_erp.services.planning import PlanningService


def make_service(conn):
    planning = PlanningService(periods=[], translate=lambda he, en: en)
    return InventoryService(conn, lambda he, en: en, planning.parse_date, planning.eta_to_week)


def add_raw_batch(conn, sku, batch_no, grams, expiry):
    conn.execute(
        "INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, source, status) "
        "VALUES (?,?,0,?,?,?,'TEST','Active')",
        (sku, batch_no, grams, expiry, date.today().isoformat()),
    )
    conn.commit()


def test_fefo_takes_earliest_expiry_first(conn):
    svc = make_service(conn)
    soon = (date.today() + timedelta(days=10)).isoformat()
    later = (date.today() + timedelta(days=200)).isoformat()
    add_raw_batch(conn, "TEST1", "LATE", 1000, later)
    add_raw_batch(conn, "TEST1", "SOON", 1000, soon)
    picks, short = svc.plan_fefo("TEST1", 500, True)
    assert [p["batch_no"] for p in picks] == ["SOON"]
    assert short == 0


def test_fefo_skips_expired_batches_by_default(conn):
    svc = make_service(conn)
    expired = (date.today() - timedelta(days=1)).isoformat()
    add_raw_batch(conn, "TEST1", "OLD", 1000, expired)
    picks, short = svc.plan_fefo("TEST1", 500, True)
    assert picks == [] and short == 500
    picks_allowed, _ = svc.plan_fefo("TEST1", 500, True, allow_expired=True)
    assert picks_allowed[0]["batch_no"] == "OLD"


def test_fefo_reports_shortage(conn):
    svc = make_service(conn)
    add_raw_batch(conn, "TEST1", "A", 300, (date.today() + timedelta(days=5)).isoformat())
    picks, short = svc.plan_fefo("TEST1", 500, True)
    assert sum(p["take"] for p in picks) == 300
    assert short == 200


def test_apply_picks_depletes_batch(conn):
    svc = make_service(conn)
    add_raw_batch(conn, "1001", "A", 400, (date.today() + timedelta(days=5)).isoformat())
    picks, _ = svc.plan_fefo("1001", 400, True)
    svc.apply_picks(picks, True)
    status = conn.execute("SELECT status FROM Batches WHERE batch_no='A'").fetchone()[0]
    assert status == "Depleted"


def test_reconcile_logs_consumption_when_stock_drops(conn):
    svc = make_service(conn)
    before = conn.execute("SELECT SUM(weight_grams) FROM Batches WHERE sku='1001' AND status='Active'").fetchone()[0]
    conn.execute("UPDATE Catalog SET weight_grams = weight_grams - 500 WHERE sku='1001'")
    conn.commit()
    svc.reconcile_batches()
    logged = conn.execute(
        "SELECT SUM(weight_grams) FROM BatchConsumption WHERE parent_sku='ADJUST' AND component_sku='1001'"
    ).fetchone()[0]
    after = conn.execute("SELECT SUM(weight_grams) FROM Batches WHERE sku='1001' AND status='Active'").fetchone()[0]
    assert logged == 500
    assert abs((before - after) - 500) < 1e-6
    moved = conn.execute("SELECT from_wh, to_wh, weight_grams FROM StockMovements WHERE reference LIKE 'ADJ%'").fetchall()
    assert moved == [("WH_RAW", "ADJUST", 500)]


def test_reconcile_adds_adjust_batch_when_stock_rises(conn):
    svc = make_service(conn)
    conn.execute("UPDATE Catalog SET weight_grams = weight_grams + 250 WHERE sku='1001'")
    conn.commit()
    svc.reconcile_batches()
    adj = conn.execute("SELECT weight_grams, source FROM Batches WHERE batch_no LIKE 'ADJ-1001-%'").fetchone()
    assert adj == (250, "ADJUST")


def test_batch_exists(conn):
    svc = make_service(conn)
    assert svc.batch_exists("1001", "OPEN-1001")
    assert not svc.batch_exists("1001", "NOPE")


def test_gen_batch_no_changes_after_a_batch_is_added(conn):
    svc = make_service(conn)
    first = svc.gen_batch_no("1001")
    add_raw_batch(conn, "1001", first, 10, "")
    assert svc.gen_batch_no("1001") != first
