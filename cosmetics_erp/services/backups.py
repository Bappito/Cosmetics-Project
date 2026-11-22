from __future__ import annotations

import json
import sqlite3
from datetime import datetime

import pandas as pd


SCOPES = {
    "stock": ["Catalog", "Batches", "BatchConsumption", "StockMovements", "PurchaseOrders", "BOM"],
    "schedule": ["WeeklySchedule"],
}
MAX_BACKUPS_PER_SCOPE = 20

class BackupService:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def push_backup(self, scope, label):
        payload = {}
        for t in SCOPES[scope]:
            payload[t] = json.loads(pd.read_sql(f"SELECT * FROM {t}", self.conn).to_json(orient="records", force_ascii=False))
        self.conn.execute(
            "INSERT INTO TableBackups (scope, label, created_at, payload) VALUES (?,?,?,?)",
            (scope, label, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(payload, ensure_ascii=False))
        )
        self.conn.execute(
            "DELETE FROM TableBackups WHERE scope=? AND backup_id NOT IN "
            "(SELECT backup_id FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT ?)",
            (scope, scope, MAX_BACKUPS_PER_SCOPE)
        )
        self.conn.commit()

    def last_backup(self, scope):
        return self.conn.execute(
            "SELECT backup_id, label, created_at FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT 1", (scope,)
        ).fetchone()

    def undo_last(self, scope):
        row = self.conn.execute(
            "SELECT backup_id, label, payload FROM TableBackups WHERE scope=? ORDER BY backup_id DESC LIMIT 1", (scope,)
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row[2])
        for t, recs in payload.items():
            self.conn.execute(f"DELETE FROM {t}")
            for rec in recs:
                cols = list(rec.keys())
                self.conn.execute(
                    f"INSERT INTO {t} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [rec[k] for k in cols]
                )
        self.conn.execute("DELETE FROM TableBackups WHERE backup_id=?", (row[0],))
        self.conn.commit()
        return row[1]
