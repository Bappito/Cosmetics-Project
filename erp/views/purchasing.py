"""Purchase orders (edit and receive) and the eight-week purchase planning (MRP)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect

from cosmetics_erp.formatting import format_date
from cosmetics_erp.services.change_review import summarize_editor_changes
from cosmetics_erp.services.mrp import monthly_summary, mrp_suggestions, week_starts, weekly_excel_bytes
from cosmetics_erp.services.planning import get_plan_start

from .page import Page

PO_STATUSES = ("Draft", "In Transit", "Confirmed", "Received", "Cancelled")
CLOSED = ("Received", "Cancelled")
WEIGHT_TYPES = ("RAW", "BULK")
PO_FIELDS = [
    "po_id", "po_number", "sku", "supplier", "order_qty_units", "order_weight_grams",
    "unit_price", "order_date", "eta_date", "target_wh", "status",
]
EDIT_NEW_ROWS = 3
PENDING_PO = "po"
PENDING_RECEIPT = "receipt"


def _blank(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _num(text: str):
    try:
        return float(str(text).replace(",", "").strip())
    except ValueError:
        return None


# Editor

def _parse_po_post(page: Page, post, cat_skus: set[str]):
    """Read the PO editor rows. Returns (rows to keep, validation errors)."""
    L = page.L
    count = int(post.get("row_count", "0") or 0)
    rows = []
    for i in range(count):
        if post.get(f"delete_{i}"):
            continue
        row = {f: post.get(f"{f}_{i}", "").strip() for f in PO_FIELDS}
        if not any(row[f] for f in ("po_number", "sku", "supplier", "order_qty_units", "order_weight_grams", "eta_date")):
            continue
        rows.append(row)

    errors = []
    if any(not r["po_number"] or not r["sku"] for r in rows):
        errors.append(L("לכל הזמנה נדרשים מספר PO ומק\"ט.", "Every order needs both a PO number and an SKU."))
    numbers = [r["po_number"] for r in rows if r["po_number"]]
    dupes = sorted({n for n in numbers if numbers.count(n) > 1})
    if dupes:
        errors.append(L(f"מספרי PO כפולים: {', '.join(dupes)}.", f"Duplicate PO numbers: {', '.join(dupes)}."))
    unknown = sorted({r["sku"] for r in rows if r["sku"] and r["sku"] not in cat_skus})
    if unknown:
        errors.append(L(f"מק\"טים שלא קיימים בקטלוג: {', '.join(unknown)}.", f"SKUs not found in the catalog: {', '.join(unknown)}."))
    for r in rows:
        for field in ("order_qty_units", "order_weight_grams", "unit_price"):
            if r[field] and (_num(r[field]) is None or _num(r[field]) < 0):
                errors.append(L("כמויות ומחירים חייבים להיות מספרים שאינם שליליים.", "Quantities and prices must be valid non-negative numbers."))
                return rows, errors
    if any(r["status"] and r["status"] not in PO_STATUSES for r in rows):
        errors.append(L("נמצאו סטטוסים לא מוכרים בהזמנות.", "One or more orders have an unsupported status."))
    return rows, errors


def _po_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=PO_FIELDS)


def _po_changes(before_rows: list[dict], after_rows: list[dict]):
    compare = [c for c in PO_FIELDS if c not in ("po_id", "po_number")]
    return summarize_editor_changes(_po_frame(before_rows), _po_frame(after_rows), "po_number", compare)


def _po_rows_from_db(conn) -> list[dict]:
    df = pd.read_sql("SELECT * FROM PurchaseOrders ORDER BY po_id DESC", conn)
    return [{f: _blank(r[f]) if f != "po_id" else int(r[f]) for f in PO_FIELDS} for _, r in df.iterrows()]


def _save_po(page: Page, rows: list[dict]) -> None:
    conn = page.conn
    existing = {int(r[0]) for r in conn.execute("SELECT po_id FROM PurchaseOrders").fetchall()}
    kept = set()
    for r in rows:
        values = (
            r["po_number"], r["sku"], r["supplier"],
            _num(r["order_qty_units"]) or 0.0, _num(r["order_weight_grams"]) or 0.0, _num(r["unit_price"]) or 0.0,
            r["order_date"], r["eta_date"], r["target_wh"] or "WH_RAW", r["status"] or "In Transit",
        )
        row_id = int(r["po_id"]) if r.get("po_id") not in (None, "", "None") else None
        if row_id in existing:
            conn.execute("""
                UPDATE PurchaseOrders SET po_number=?, sku=?, supplier=?, order_qty_units=?, order_weight_grams=?,
                    unit_price=?, order_date=?, eta_date=?, target_wh=?, status=?
                WHERE po_id=?
            """, (*values, row_id))
            kept.add(row_id)
        else:
            conn.execute("""
                INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status)
                VALUES (?,?,?,?,?,?,?,?,?,?)
            """, values)
    for removed in existing - kept:
        conn.execute("DELETE FROM PurchaseOrders WHERE po_id=?", (removed,))
    conn.commit()


def _po_action(page: Page, action: str) -> None:
    L = page.L
    cat_skus = {r[0] for r in page.conn.execute("SELECT sku FROM Catalog").fetchall()}
    if action == "review":
        before = _po_rows_from_db(page.conn)
        rows, errors = _parse_po_post(page, page.request.POST, cat_skus)
        if errors:
            for e in errors:
                page.error(e)
            return
        added, removed, changed = _po_changes(before, rows)
        if not (added or removed or changed):
            page.error(L("אין שינויים לשמירה.", "No changes to save."))
            return
        page.set_pending(PENDING_PO, {"rows": rows, "added": added, "removed": removed, "changed": changed})
    elif action == "confirm":
        review = page.pending(PENDING_PO)
        if not review or not page.request.POST.get("confirmed"):
            page.error(L("יש לאשר את השינויים לפני השמירה.", "Confirm the changes before saving."))
            return
        page.push_backup("stock", L("שמירת הזמנות רכש", "PO save"))
        _save_po(page, review["rows"])
        page.clear_pending(PENDING_PO)
        page.flash(L("נשמר!", "Saved!"))
    elif action == "cancel":
        page.clear_pending(PENDING_PO)


# Receiving

def _receipt_action(page: Page, action: str, open_rows: dict) -> None:
    L = page.L
    post = page.request.POST
    if action == "review":
        po_number = post.get("po_number", "")
        po = open_rows.get(po_number)
        if not po:
            page.error(L("ההזמנה כבר אינה פתוחה.", "That order is no longer open."))
            return
        is_w = po["item_type"] in WEIGHT_TYPES
        amount = po["amount"]
        if amount <= 0:
            page.error(L("כמות ההזמנה חייבת להיות גדולה מאפס.", "The order quantity must be greater than zero."))
            return
        batch = post.get("batch", "").strip() or page.inventory.gen_batch_no(po["sku"])
        no_expiry = bool(post.get("no_expiry"))
        expiry = "" if no_expiry else (post.get("expiry") or "")
        if not no_expiry:
            try:
                date.fromisoformat(expiry)
            except ValueError:
                page.error(L("יש להזין תאריך תפוגה תקין.", "Enter a valid expiry date."))
                return
        page.set_pending(PENDING_RECEIPT, {
            "po_number": po_number, "sku": po["sku"], "amount": amount, "is_weight": is_w,
            "batch": batch, "expiry": expiry, "target_wh": po["target_wh"] or "WH_RAW",
        })
    elif action == "confirm":
        r = page.pending(PENDING_RECEIPT)
        if not r or not post.get("confirmed"):
            page.error(L("יש לאשר את הקבלה לפני העדכון.", "Confirm the receipt before updating stock."))
            return
        if page.batch_exists(r["sku"], r["batch"]):
            page.error(L(f"אצווה {r['batch']} כבר קיימת למק\"ט {r['sku']}. ערוך/י את מספר האצווה.",
                         f"Batch {r['batch']} already exists for SKU {r['sku']}. Edit the batch number."))
            return
        page.push_backup("stock", f"{L('קבלת', 'Receive')} {r['po_number']}")
        page.inventory.add_batch(r["sku"], r["batch"], r["amount"], r["is_weight"], r["expiry"], "PO")
        page.inventory.log_move(r["sku"], "WH_VENDOR", r["target_wh"], r["amount"], r["is_weight"], f"{r['po_number']} / {r['batch']}")
        stamp = datetime.now().strftime("%Y-%m-%d")
        if r["is_weight"]:
            page.conn.execute(
                "UPDATE Catalog SET weight_grams = weight_grams + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                (r["amount"], f"+{r['amount'] / 1000:.2f} ק\"ג מקבלת {r['po_number']}", f"{stamp} (+{r['amount'] / 1000:.2f} ק\"ג)", r["sku"]),
            )
        else:
            page.conn.execute(
                "UPDATE Catalog SET qty_units = qty_units + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
                (r["amount"], f"+{r['amount']:.0f} יח' מקבלת {r['po_number']}", f"{stamp} (+{r['amount']:.0f} יח')", r["sku"]),
            )
        page.conn.execute("UPDATE PurchaseOrders SET status='Received' WHERE po_number=?", (r["po_number"],))
        page.conn.commit()
        page.clear_pending(PENDING_RECEIPT)
        page.flash(L(f"הזמנה {r['po_number']} התקבלה: אצווה {r['batch']}, תפוגה {r['expiry'] or 'ללא'}.",
                     f"Order {r['po_number']} received: batch {r['batch']}, expiry {r['expiry'] or 'none'}."))
    elif action == "cancel":
        page.clear_pending(PENDING_RECEIPT)


def _open_orders(page: Page) -> dict:
    """Open POs keyed by PO number, with the catalog type and the ordered base amount."""
    rows = page.conn.execute("""
        SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.target_wh, c.item_type
        FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku
        WHERE po.status NOT IN ('Received','Cancelled') ORDER BY po.eta_date ASC, po.po_number
    """).fetchall()
    out = {}
    for po_number, sku, qty, grams, target, item_type in rows:
        is_w = item_type in WEIGHT_TYPES
        out[po_number] = {
            "sku": sku, "item_type": item_type or "RAW", "target_wh": target,
            "amount": float(grams or 0) if is_w else float(qty or 0),
        }
    return out


@login_required
def purchase_orders(request):
    if request.method == "POST":
        with Page(request, "purchase_orders", edit=True) as page:
            action = request.POST.get("action", "")
            if action.startswith("po_"):
                _po_action(page, action[3:])
            elif action.startswith("receipt_"):
                _receipt_action(page, action[8:], _open_orders(page))
            return redirect("purchase_orders")

    with Page(request, "purchase_orders") as page:
        L = page.L
        df_all = pd.read_sql("SELECT po.*, c.name, c.item_type FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku ORDER BY po.po_id DESC", page.conn)
        open_df = df_all[~df_all["status"].isin(list(CLOSED))]
        query = request.GET.get("q", "").strip()
        status = request.GET.get("status", "")

        open_rows = []
        filtered = open_df
        if status:
            filtered = filtered[filtered["status"] == status]
        if query:
            cols = filtered[["po_number", "sku", "supplier", "status"]].fillna("").astype(str)
            filtered = filtered[cols.apply(lambda c: c.str.contains(query, case=False, regex=False)).any(axis=1)]
        for r in filtered.itertuples():
            is_w = r.item_type in WEIGHT_TYPES
            amount = float(r.order_weight_grams if is_w else r.order_qty_units or 0)
            open_rows.append({
                "po_number": r.po_number, "supplier": _blank(r.supplier),
                "amount": page.fmt(amount, is_w),
                "eta": format_date(r.eta_date, is_he=page.is_he),
                "week": page.planning.eta_week_label(r.eta_date),
                "status": r.status, "name": _blank(r.name) or "?", "sku": r.sku,
            })

        review = page.pending(PENDING_PO)
        editable = None
        if not review:
            editable = _po_rows_from_db(page.conn) + [dict.fromkeys(PO_FIELDS, "") for _ in range(EDIT_NEW_ROWS)]
        receipt_orders = _open_orders(page)
        receipt = page.pending(PENDING_RECEIPT)
        receipt_view = None
        if receipt_orders:
            selected = request.GET.get("po") or (receipt["po_number"] if receipt else next(iter(receipt_orders)))
            if selected not in receipt_orders:
                selected = next(iter(receipt_orders))
            po = receipt_orders[selected]
            receipt_view = {
                "po_number": selected, "sku": po["sku"], "target_wh": po["target_wh"] or "WH_RAW",
                "amount_text": page.fmt(po["amount"], po["item_type"] in WEIGHT_TYPES),
                "is_weight": po["item_type"] in WEIGHT_TYPES,
                "default_batch": f"LOT-{po['sku']}-{selected}",
                "default_expiry": (date.today() + timedelta(days=365)).isoformat(),
                "no_expiry_default": po["item_type"] == "PKG",
                "valid": po["amount"] > 0,
            }

        return page.render(
            "erp/purchase_orders.html",
            title=L("ניהול הזמנות רכש (PO)", "Purchase orders (PO)"),
            subtitle=L("ערוך/י הזמנות, בדוק/י שבוע הגעה בסימולטורים וקבל/י הזמנה למחסן.",
                       "Edit orders, check the arrival week in the simulators, and receive an order into a warehouse."),
            open_count=len(open_df),
            open_rows=open_rows,
            q=query,
            status=status,
            statuses=sorted(open_df["status"].dropna().unique()),
            po_statuses=PO_STATUSES,
            editable=editable,
            po_review=review,
            receipt_orders=list(receipt_orders),
            receipt=receipt,
            receipt_view=receipt_view,
            here=request.get_full_path(),
        )


@login_required
def po_list(request):
    """Read-only list of every purchase order (all statuses), with search and a status filter.

    Editing and receiving stay on the separate management screen (purchase_orders).
    """
    with Page(request, "po_list") as page:
        L = page.L
        df = pd.read_sql(
            "SELECT po.*, c.name, c.item_type FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku "
            "ORDER BY po.eta_date ASC, po.po_number",
            page.conn,
        )
        query = request.GET.get("q", "").strip()
        status = request.GET.get("status", "")

        filtered = df
        if status:
            filtered = filtered[filtered["status"] == status]
        if query:
            cols = filtered[["po_number", "sku", "name", "supplier", "status"]].fillna("").astype(str)
            filtered = filtered[cols.apply(lambda c: c.str.contains(query, case=False, regex=False)).any(axis=1)]

        rows = []
        for r in filtered.itertuples():
            is_w = r.item_type in WEIGHT_TYPES
            amount = float(r.order_weight_grams if is_w else (r.order_qty_units or 0))
            rows.append({
                "po_number": r.po_number, "sku": r.sku, "name": _blank(r.name) or "?",
                "supplier": _blank(r.supplier), "amount": page.fmt(amount, is_w),
                "eta": format_date(r.eta_date, is_he=page.is_he),
                "week": page.planning.eta_week_label(r.eta_date),
                "status": r.status, "is_open": r.status not in CLOSED,
            })

        open_count = int((~df["status"].isin(list(CLOSED))).sum())
        return page.render(
            "erp/po_list.html",
            title=L("הזמנות רכש", "Purchase orders"),
            subtitle=L("כל ההזמנות לפי תאריך הגעה. לעריכה וקבלה עבור ל\"ניהול הזמנות רכש\".",
                       "Every order by arrival date. To edit or receive, go to Purchase orders management."),
            total=len(df),
            open_count=open_count,
            suppliers=int(df["supplier"].dropna().nunique()),
            skus=int(df["sku"].nunique()),
            rows=rows,
            shown=len(rows),
            q=query,
            status=status,
            statuses=sorted(df["status"].dropna().unique()),
        )


# MRP

def _mrp_inputs(page: Page):
    catalog = pd.read_sql(
        "SELECT sku, name, item_type, qty_units, weight_grams, min_order_qty, main_supplier, primary_warehouse FROM Catalog",
        page.conn,
    )
    bom = pd.read_sql("SELECT parent_sku, component_sku, req_qty_units, req_weight_grams FROM BOM", page.conn)
    schedule = pd.read_sql("SELECT parent_sku, W1, W2, W3, W4, W5, W6, W7, W8 FROM WeeklySchedule", page.conn)
    po_rows = pd.read_sql(
        "SELECT po.po_number, po.sku, po.order_qty_units, po.order_weight_grams, po.eta_date, c.item_type "
        "FROM PurchaseOrders po LEFT JOIN Catalog c ON po.sku = c.sku WHERE po.status NOT IN ('Received', 'Cancelled')",
        page.conn,
    )
    po_rows["qty_base"] = [
        float(w if t in WEIGHT_TYPES else u or 0.0)
        for w, u, t in zip(po_rows["order_weight_grams"], po_rows["order_qty_units"], po_rows["item_type"])
    ]
    po_rows["week"] = po_rows["eta_date"].map(page.planning.eta_to_week)
    suggestions = mrp_suggestions(catalog, bom, schedule, po_rows)
    return catalog, suggestions


MRP_HEADERS_HE = ["מק\"ט", "פריט", "סוג", "שבוע", "תחילת שבוע", "סוף שבוע", "חודש", "חסר", "להזמין", "יחידה", "ספק"]
MRP_HEADERS_EN = ["SKU", "Item", "Type", "Week", "Week start", "Week end", "Month", "Short", "To order", "Unit", "Supplier"]


@login_required
def mrp_export(request):
    with Page(request, "mrp") as page:
        _catalog, suggestions = _mrp_inputs(page)
        headers = MRP_HEADERS_HE if page.is_he else MRP_HEADERS_EN
        data = weekly_excel_bytes(suggestions, page.plan_start, headers) if not suggestions.empty else b""
        response = HttpResponse(
            data,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = f'attachment; filename="mrp-weekly-{date.today():%Y%m%d}.xlsx"'
        return response


@login_required
def mrp(request):
    if request.method == "POST":
        with Page(request, "mrp", edit=True) as page:
            if request.POST.get("action") != "create" or not request.POST.get("confirmed"):
                page.error(page.L("יש לאשר את היצירה לפני יצירת ההזמנות.", "Confirm before creating draft orders."))
                return redirect("mrp")
            catalog, suggestions = _mrp_inputs(page)
            if suggestions.empty:
                page.error(page.L("אין הצעות לרכש.", "No suggestions to order."))
                return redirect("mrp")
            summary = monthly_summary(suggestions, page.plan_start).copy()
            page.push_backup("stock", page.L("תכנון רכש (MRP)", "MRP draft orders"))
            stamp = datetime.now().strftime("%y%m%d")
            cat_idx = catalog.set_index("sku")
            first_week = week_starts(page.plan_start).groupby("month")["week_start"].min()
            for n, row in enumerate(summary.itertuples(), start=1):
                is_w = row.item_type in WEIGHT_TYPES
                eta = first_week[row.month].strftime("%Y-%m-%d")
                target_wh = cat_idx.loc[row.sku, "primary_warehouse"] or "WH_RAW"
                page.conn.execute(
                    "INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, unit_price, order_date, eta_date, target_wh, status) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"MRP-{stamp}-{n:03d}", row.sku, row.supplier,
                        0.0 if is_w else float(row.order_base), float(row.order_base) if is_w else 0.0,
                        0.0, date.today().strftime("%Y-%m-%d"), eta, target_wh, "Draft",
                    ),
                )
            page.conn.commit()
            page.flash(page.L(f"נוצרו {len(summary)} הזמנות טיוטה (לפי חודש).", f"Created {len(summary)} draft orders (by month)."))
        return redirect("mrp")

    with Page(request, "mrp") as page:
        catalog, suggestions = _mrp_inputs(page)
        table = []
        if not suggestions.empty:
            summary = monthly_summary(suggestions, page.plan_start).copy()
            for r in summary.itertuples():
                is_w = r.item_type in WEIGHT_TYPES
                table.append({
                    "sku": r.sku, "name": r.name, "month": r.month,
                    "short": page.fmt(float(r.shortfall_base), is_w),
                    "order": page.fmt(float(r.order_base), is_w),
                    "supplier": _blank(r.supplier),
                })
            drafts_count = len(summary)
        else:
            drafts_count = 0
        return page.render(
            "erp/mrp.html",
            title=page.L("תכנון רכש (MRP)", "Purchase planning (MRP)"),
            subtitle=page.L(
                "מחשב מה צריך לקנות לפי תוכנית 8 השבועות, המלאי הנוכחי, ההזמנות הפתוחות וה-BOM. ההצעות מעוגלות לכמות ההזמנה המינימלית (MOQ).",
                "Works out what to buy from the 8-week plan, current stock, open purchase orders, and the BOM. Suggestions are rounded up to the minimum order quantity (MOQ).",
            ),
            table=table,
            has_suggestions=not suggestions.empty,
            drafts_count=drafts_count,
        )
