from cosmetics_erp.services.backups import MAX_BACKUPS_PER_SCOPE, BackupService


def test_undo_restores_catalog_snapshot(conn):
    backups = BackupService(conn)
    before = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='1001'").fetchone()[0]
    backups.push_backup("stock", "test change")
    conn.execute("UPDATE Catalog SET weight_grams = 1 WHERE sku='1001'")
    conn.commit()
    assert backups.undo_last("stock") == "test change"
    restored = conn.execute("SELECT weight_grams FROM Catalog WHERE sku='1001'").fetchone()[0]
    assert restored == before


def test_only_latest_backups_are_kept(conn):
    backups = BackupService(conn)
    for i in range(MAX_BACKUPS_PER_SCOPE + 5):
        backups.push_backup("stock", f"b{i}")
    count = conn.execute("SELECT COUNT(*) FROM TableBackups WHERE scope='stock'").fetchone()[0]
    assert count == MAX_BACKUPS_PER_SCOPE


def test_undo_with_no_backup_returns_none(conn):
    assert BackupService(conn).undo_last("schedule") is None
