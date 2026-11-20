from __future__ import annotations

import sqlite3
from datetime import date, datetime
from typing import Callable

import pandas as pd


class InventoryService:
    def __init__(
        self,
        conn: sqlite3.Connection,
        translate: Callable[[str, str], str],
        parse_date: Callable[[object], date | None],
        eta_to_week: Callable[[object], str | None],
    ) -> None:
        self.conn = conn
        self.translate = translate
        self.parse_date = parse_date
        self.eta_to_week = eta_to_week

    def get_incoming_map(self):
        df = pd.read_sql(
            "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
            "FROM PurchaseOrders po JOIN Catalog c ON po.sku = c.sku "
            "WHERE po.status NOT IN ('Received','Cancelled')", self.conn
        )
        out = {}
        for r in df.itertuples():
            wk = self.eta_to_week(r.eta_date)
            if not wk:
                continue
            is_w_po = r.item_type in ("RAW", "BULK")
            amt = float(r.order_weight_grams if is_w_po else r.order_qty_units)
            ent = out.setdefault((r.sku, wk), {"amt": 0.0, "pos": []})
            ent["amt"] += amt
            ent["pos"].append(str(r.po_number))
        return out

    def get_sku_expiry_summary(self):
        df_b = pd.read_sql(
            "SELECT sku, batch_no, expiry_date FROM Batches WHERE status='Active' "
            "ORDER BY CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END, expiry_date ASC",
            self.conn
        )
        summary = {}
        today_d = date.today()
        for _, r in df_b.iterrows():
            s = r["sku"]
            if s not in summary:
                exp_s = str(r["expiry_date"] or "").strip()
                d_obj = self.parse_date(exp_s)
                if d_obj is None:
                    badge = f"<span class='exp-badge-ok'>{self.translate('ללא תפוגה', 'No Expiry')}</span>"
                else:
                    days_l = (d_obj - today_d).days
                    if days_l < 0:
                        badge = f"<span class='exp-badge-bad'>{exp_s} ({self.translate('פג תוקף', 'Expired')})</span>"
                    elif days_l <= 30:
                        badge = f"<span class='exp-badge-warn'>{exp_s} ({days_l} {self.translate('ימים', 'days')})</span>"
                    else:
                        badge = f"<span class='exp-badge-ok'>{exp_s}</span>"
                summary[s] = {"batch_no": r["batch_no"], "expiry_html": badge}
        return summary

    def batch_col(self, is_w):
        return "weight_grams" if is_w else "qty_units"

    def plan_fefo(self, sku, amount, is_w, allow_expired=False):
        col = self.batch_col(is_w)
        rows = self.conn.execute(
            f"SELECT batch_id, batch_no, expiry_date, {col} FROM Batches "
            f"WHERE sku=? AND status='Active' AND {col} > 0.000001 "
            f"ORDER BY CASE WHEN expiry_date IS NULL OR expiry_date='' THEN 1 ELSE 0 END, expiry_date, received_date, batch_id",
            (sku,)
        ).fetchall()
        today_d = date.today()
        picks = []
        remaining = float(amount)
        for bid, bno, exp, have in rows:
            if remaining <= 1e-9:
                break
            ed = self.parse_date(exp)
            if ed is not None and ed < today_d and not allow_expired:
                continue
            take = min(float(have), remaining)
            picks.append({"batch_id": bid, "batch_no": bno, "expiry": exp or "", "take": take})
            remaining -= take
        return picks, max(0.0, remaining)

    def apply_picks(self, picks, is_w):
        col = self.batch_col(is_w)
        for p in picks:
            self.conn.execute(f"UPDATE Batches SET {col} = MAX(0, {col} - ?) WHERE batch_id = ?", (p["take"], p["batch_id"]))
        self.conn.execute("UPDATE Batches SET status='Depleted' WHERE status='Active' AND weight_grams <= 0.000001 AND qty_units <= 0.000001")

    def add_batch(self, sku, batch_no, amount, is_w, expiry, source):
        today_s = date.today().strftime("%Y-%m-%d")
        col = self.batch_col(is_w)
        row = self.conn.execute("SELECT batch_id FROM Batches WHERE sku=? AND batch_no=?", (sku, batch_no)).fetchone()
        if row:
            self.conn.execute(
                f"UPDATE Batches SET {col} = {col} + ?, status='Active', "
                f"expiry_date = CASE WHEN COALESCE(expiry_date,'')='' THEN ? ELSE expiry_date END WHERE batch_id=?",
                (amount, expiry or "", row[0])
            )
        else:
            self.conn.execute("""
                INSERT INTO Batches (sku, batch_no, qty_units, weight_grams, expiry_date, received_date, source, status)
                VALUES (?,?,?,?,?,?,?,'Active')
            """, (sku, batch_no, 0.0 if is_w else amount, amount if is_w else 0.0, expiry or "", today_s, source))

    def log_move(self, sku, from_wh, to_wh, amount, is_w, reference):
        self.conn.execute("""
            INSERT INTO StockMovements (move_date, sku, from_wh, to_wh, qty_units, weight_grams, reference)
            VALUES (?,?,?,?,?,?,?)
        """, (datetime.now().strftime("%Y-%m-%d %H:%M"), sku, from_wh, to_wh,
              0.0 if is_w else amount, amount if is_w else 0.0, reference))

    def log_consumption(self, parent_sku, parent_batch, comp_sku, picks, is_w, reference):
        now_s = datetime.now().strftime("%Y-%m-%d %H:%M")
        for p in picks:
            self.conn.execute("""
                INSERT INTO BatchConsumption (move_date, parent_sku, parent_batch, component_sku, component_batch, qty_units, weight_grams, reference)
                VALUES (?,?,?,?,?,?,?,?)
            """, (now_s, parent_sku, parent_batch, comp_sku, p["batch_no"],
                  0.0 if is_w else p["take"], p["take"] if is_w else 0.0, reference))

    def gen_batch_no(self, sku):
        today_s = date.today().strftime("%Y-%m-%d")
        n = self.conn.execute("SELECT COUNT(*) FROM Batches WHERE sku=? AND received_date=?", (sku, today_s)).fetchone()[0] + 1
        return f"L{sku}-{date.today().strftime('%y%m%d')}-{n:02d}"

    def reconcile_batches(self):
        self.conn.execute("DELETE FROM Batches WHERE sku NOT IN (SELECT sku FROM Catalog)")
        cat = self.conn.execute("SELECT sku, item_type, qty_units, weight_grams FROM Catalog").fetchall()
        today_s = date.today().strftime("%Y-%m-%d")
        for sku, tp, qu, wg in cat:
            is_w = tp in ("RAW", "BULK")
            col = self.batch_col(is_w)
            target = float(wg if is_w else qu)
            cur = float(self.conn.execute(
                f"SELECT COALESCE(SUM({col}),0) FROM Batches WHERE sku=? AND status='Active'", (sku,)
            ).fetchone()[0] or 0)
            diff = target - cur
            if diff > 1e-6:
                self.add_batch(sku, f"ADJ-{sku}-{today_s.replace('-', '')}", diff, is_w, "", "ADJUST")
            elif diff < -1e-6:
                picks, _ = self.plan_fefo(sku, -diff, is_w, allow_expired=True)
                self.apply_picks(picks, is_w)
        self.conn.commit()

    def trace_chain(self, sku, batch_no, direction):
        rows = []
        frontier = [(sku, batch_no)]
        seen = set(frontier)
        level = 0
        while frontier and level < 6:
            level += 1
            nxt = []
            for s, b in frontier:
                if direction == "back":
                    q = self.conn.execute(
                        "SELECT component_sku, component_batch, qty_units, weight_grams, move_date, reference "
                        "FROM BatchConsumption WHERE parent_sku=? AND parent_batch=?", (s, b)).fetchall()
                else:
                    q = self.conn.execute(
                        "SELECT parent_sku, parent_batch, qty_units, weight_grams, move_date, reference "
                        "FROM BatchConsumption WHERE component_sku=? AND component_batch=?", (s, b)).fetchall()
                for r in q:
                    rows.append((level,) + tuple(r))
                    key = (r[0], r[1])
                    if key not in seen:
                        seen.add(key)
                        nxt.append(key)
            frontier = nxt
        return rows
