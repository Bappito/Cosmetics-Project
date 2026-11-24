"""Warehouses: stock and expiry, purchase orders, suppliers, the catalog editor, physical count and ERP import.

Editing follows the same steps everywhere: changes are checked, reviewed, confirmed and only
then saved. A backup is taken before each save so it can be undone.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from cosmetics_erp.formatting import format_date
from cosmetics_erp.services.change_review import summarize_editor_changes
from cosmetics_erp.services.erp_import import build_po_rows, build_stock_rows, guess_column, read_table
from cosmetics_erp.text_language import localize_text

from .page import Page

WEIGHT_TYPES = ("RAW", "BULK")
ITEM_TYPES = ("RAW", "BULK", "PKG", "FG")
PO_STATUSES = ("Draft", "In Transit", "Confirmed", "Received", "Cancelled")
CATALOG_FIELDS = [
    "sku", "name", "item_type", "stock_val", "open_orders", "stock_movements",
    "main_supplier", "alt_suppliers", "last_stock_entry",
]
NEW_ROWS = 3  # blank rows offered in editors, instead of the dynamic rows of the old editor
PENDING_CATALOG = "catalog"
PENDING_COUNT = "count"
PENDING_IMPORT_FILE = "import_file"
PENDING_IMPORT = "import"


def _warehouses(page: Page):
    return [
        ("RAW", page.L("1. מחסן חומר גלם (RAW)", "1. Raw materials WH")),
        ("BULK", page.L("2. מחסן בלקים - חומר שהוכן (BULK)", "2. Bulks WH")),
        ("PKG", page.L("3. מחסן אריזות (PKG)", "3. Packaging WH")),
        ("COL", page.L("4. מחסן צבעים (שיער)", "4. Colours WH (hair)")),
    ]


TABS = [
    ("stock", "מלאי נוכחי ותאריכי תפוגה", "Current stock & expiry dates"),
    ("po", "הזמנות רכש (PO)", "Purchase orders (PO)"),
    ("sup", "ספקים ותנועות מלאי", "Suppliers & stock movements"),
    ("edit", "עריכה והוספת פריטים", "Edit & add items"),
    ("count", "עדכון לפי ספירה", "Update by count"),
    ("import", "ייבוא ERP", "ERP import"),
]


def _subset(df_cat: pd.DataFrame, wh: str) -> pd.DataFrame:
    if wh == "COL":
        return df_cat[(df_cat["item_type"] == "RAW") & (df_cat["primary_warehouse"] == "WH_COLOR")]
    if wh == "RAW":
        return df_cat[(df_cat["item_type"] == "RAW") & (df_cat["primary_warehouse"] != "WH_COLOR")]
    return df_cat[df_cat["item_type"] == wh]


def _clean(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _apply_stock(conn, rows: list[dict], types: dict[str, str], reconcile) -> None:
    """Set catalog balances to the counted values, then reconcile batches (which logs ADJUST movements)."""
    stamp = datetime.now().strftime("%Y-%m-%d") + " (ספירה)"
    for row in rows:
        column = "weight_grams" if types.get(row["sku"]) in WEIGHT_TYPES else "qty_units"
        conn.execute(f"UPDATE Catalog SET {column} = ?, last_stock_entry = ? WHERE sku = ?",
                     (float(row["counted"]), stamp, row["sku"]))
    conn.commit()
    reconcile()


# Read-only tabs

def _stock_tab(page: Page, df_wh: pd.DataFrame, is_w: bool, query: str):
    expiry = page.inventory.get_sku_expiry_summary()
    view = df_wh
    if query:
        mask = (
            view["sku"].astype(str).str.contains(query, case=False, na=False, regex=False)
            | view["name"].astype(str).str.contains(query, case=False, na=False, regex=False)
        )
        view = view[mask]
    rows = []
    for _, r in view.iterrows():
        info = expiry.get(str(r["sku"]), {"batch_no": "-", "expiry_html": "-"})
        rows.append({
            "sku": str(r["sku"]),
            "name": _clean(r["name"]),
            "stock": page.fmt(float(r["weight_grams"] if is_w else r["qty_units"]), is_w),
            "batch_no": _clean(info["batch_no"]),
            # The expiry badge is built by the service from escaped text.
            "expiry_html": info["expiry_html"],
        })
    return {"rows": rows, "query": query, "shown": len(view), "total": len(df_wh)}


def _po_tab(page: Page, df_wh: pd.DataFrame, is_w: bool, df_po_open: pd.DataFrame):
    skus = set(df_wh["sku"])
    names = df_wh.set_index("sku")["name"].to_dict()
    rows = []
    for _, pr in df_po_open[df_po_open["sku"].isin(skus)].iterrows():
        amount = float(pr["order_weight_grams"] if is_w else pr["order_qty_units"])
        rows.append({
            "sku": str(pr["sku"]),
            "name": _clean(names.get(pr["sku"], "")),
            "po_number": str(pr["po_number"]),
            "supplier": _clean(pr["supplier"]),
            "amount": page.fmt(amount, is_w),
            "eta": format_date(pr["eta_date"], is_he=page.is_he),
            "week": page.planning.eta_week_label(pr["eta_date"]),
            "status": _clean(pr["status"]),
        })
    return rows


def _sup_tab(df_wh: pd.DataFrame):
    return [
        {
            "sku": str(r["sku"]), "name": _clean(r["name"]), "main": _clean(r["main_supplier"]),
            "alt": _clean(r["alt_suppliers"]), "last_entry": _clean(r["last_stock_entry"]),
            "movements": _clean(r["stock_movements"]),
        }
        for _, r in df_wh.iterrows()
    ]


# Catalog editor

def _catalog_rows_from_db(page: Page, df_cat: pd.DataFrame) -> list[dict]:
    rows = []
    for _, r in df_cat.iterrows():
        is_w = r["item_type"] in WEIGHT_TYPES
        stock_val = round(r["weight_grams"] / page.w_factor, 3) if is_w else round(float(r["qty_units"]), 0)
        rows.append({
            "sku": _clean(r["sku"]), "name": _clean(r["name"]), "item_type": _clean(r["item_type"]),
            "stock_val": stock_val, "open_orders": _clean(r["open_orders"]),
            "stock_movements": _clean(r["stock_movements"]), "main_supplier": _clean(r["main_supplier"]),
            "alt_suppliers": _clean(r["alt_suppliers"]), "last_stock_entry": _clean(r["last_stock_entry"]),
        })
    return rows


def _parse_catalog_post(page: Page, post) -> tuple[list[dict], list[str]]:
    """Read the editor rows from the form. Returns (rows to keep, validation errors)."""
    L = page.L
    count = int(post.get("row_count", "0") or 0)
    rows, errors = [], []
    stored_names = dict(page.conn.execute("SELECT sku, name FROM Catalog").fetchall())
    for i in range(count):
        if post.get(f"delete_{i}"):
            continue
        sku = post.get(f"sku_{i}", "").strip()
        name = post.get(f"name_{i}", "").strip()
        # The form showed the name in one language. If it was not changed, keep the stored two-language name.
        if sku in stored_names and name == localize_text(stored_names[sku] or "", page.lang):
            name = stored_names[sku]
        item_type = post.get(f"item_type_{i}", "RAW")
        if not sku and not name and not post.get(f"stock_val_{i}", "").strip():
            continue  # a blank row
        stock_text = post.get(f"stock_val_{i}", "").strip()
        try:
            stock_val = float(stock_text)
        except ValueError:
            stock_val = None
        row = {f: post.get(f"{f}_{i}", "").strip() for f in CATALOG_FIELDS}
        row.update({"sku": sku, "name": name, "item_type": item_type, "stock_val": stock_val})
        rows.append(row)

    skus = [r["sku"] for r in rows if r["sku"]]
    dupes = sorted({s for s in skus if skus.count(s) > 1})
    if dupes:
        errors.append(L(f"יש מק\"טים כפולים: {', '.join(dupes)}.", f"Duplicate SKUs: {', '.join(dupes)}."))
    if any(r["sku"] and not r["name"] for r in rows):
        errors.append(L("לכל מק\"ט נדרש שם פריט.", "Every SKU needs an item name."))
    if any(r["sku"] and r["item_type"] not in ITEM_TYPES for r in rows):
        errors.append(L("יש לבחור סוג פריט תקין לכל שורה.", "Select a valid item type for each row."))
    if any(r["sku"] and (r["stock_val"] is None or r["stock_val"] < 0) for r in rows):
        errors.append(L("המלאי חייב להיות מספר שאינו שלילי.", "Stock values must be valid non-negative numbers."))
    return rows, errors


def _catalog_status(page: Page, before: list[dict], rows: list[dict], errors: list[str], columns: list[str]):
    before_df = pd.DataFrame(before, columns=columns)
    after_df = pd.DataFrame(rows, columns=columns)
    changes = summarize_editor_changes(before_df, after_df, "sku", columns[:-1]) if not after_df.empty else ([], [], [])
    return {
        "editable": None,
        "errors": errors,
        "changes": {"added": changes[0], "removed": changes[1], "changed": changes[2]},
        "has_changes": any(changes),
        "rows": rows,
    }


# Count

def _count_rows(page: Page, df_wh: pd.DataFrame, is_w: bool) -> list[dict]:
    rows = []
    for _, r in df_wh.iterrows():
        system = (r["weight_grams"] / page.w_factor if is_w else r["qty_units"])
        system = round(float(system), 3)
        rows.append({"sku": str(r["sku"]), "name": _clean(r["name"]), "system": system,
                     "item_type": str(r.get("item_type", "")) if hasattr(r, "get") else ""})
    return rows


def _parse_count_post(page: Page, post, rows: list[dict], is_w: bool):
    """Returns (changed rows with counted in base units, invalid flag)."""
    changed, invalid = [], False
    for i, row in enumerate(rows):
        raw = post.get(f"counted_{i}", "").strip()
        try:
            counted = float(raw.replace(",", "."))
        except ValueError:
            invalid = True
            continue
        if counted < 0:
            invalid = True
            continue
        if abs(counted - row["system"]) > 1e-6:
            changed.append({
                "sku": row["sku"],
                "name": row["name"],
                "system": row["system"],
                "counted": counted,
                "difference": round(counted - row["system"], 3),
                "counted_base": counted * (page.w_factor if is_w else 1.0),
            })
    return changed, invalid


# ERP import

def _import_table(pending_file: dict) -> pd.DataFrame:
    return pd.DataFrame(pending_file["records"], columns=pending_file["columns"])


def _build_import(page: Page, kind: str, mapping: dict, unit: str, df: pd.DataFrame, cat: pd.DataFrame) -> dict:
    known = set(cat["sku"].astype(str))
    weight_skus = set(cat.loc[cat["item_type"].isin(WEIGHT_TYPES), "sku"].astype(str))
    factor = 1000.0 if unit == "kg" else 1.0
    if kind == "stock":
        rows_df, errors = build_stock_rows(df, mapping, known, weight_skus, factor)
        rows = [{"sku": str(r.sku), "counted": float(r.counted)} for r in rows_df.itertuples()]
    else:
        rows, errors = build_po_rows(df, mapping, known, weight_skus, factor)
        rows = [{k: (float(v) if k == "qty_base" else v) for k, v in r.items()} for r in rows]
    return {"kind": kind, "rows": rows, "errors": errors, "unit": unit, "mapping": mapping}


# View

@login_required
def inventory(request):
    if request.method == "POST":
        return _post(request)
    with Page(request, "inventory") as page:
        wh, tab = _params(request)
        return _render(page, request, wh, tab, request.GET.get("q", "").strip())


def _params(request):
    wh = request.GET.get("wh", "RAW")
    if wh not in ("RAW", "BULK", "PKG", "COL"):
        wh = "RAW"
    tab = request.GET.get("tab", "stock")
    if tab not in [t[0] for t in TABS]:
        tab = "stock"
    return wh, tab


def _post(request):
    with Page(request, "inventory", edit=True) as page:
        wh, tab = _params(request)
        action = request.POST.get("action", "")
        cat = pd.read_sql("SELECT * FROM Catalog", page.conn)
        types = cat.set_index("sku")["item_type"].to_dict()
        if tab == "edit":
            _catalog_action(page, action, cat)
        elif tab == "count":
            _count_action(page, action, cat, wh, types)
        elif tab == "import":
            _import_action(page, request, action, cat, types)
        return redirect(f"{request.path}?wh={wh}&tab={tab}")


def _catalog_action(page: Page, action: str, cat: pd.DataFrame) -> None:
    if action == "review":
        before = _catalog_rows_from_db(page, cat)
        columns = [
            "last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements",
            "open_orders", "stock_val", "item_type", "name", "sku",
        ]
        rows, errors = _parse_catalog_post(page, page.request.POST)
        if errors:
            for e in errors:
                page.error(e)
            return
        status = _catalog_status(page, before, rows, errors, columns)
        if not status["has_changes"]:
            page.error(page.L("אין שינויים לשמירה.", "No changes to save."))
            return
        page.set_pending(PENDING_CATALOG, {"rows": rows, "changes": status["changes"]})
    elif action == "confirm":
        review = page.pending(PENDING_CATALOG)
        if not review or not page.request.POST.get("confirmed"):
            page.error(page.L("יש לאשר את השינויים לפני השמירה.", "Confirm the changes before saving."))
            return
        page.push_backup("stock", page.L("שמירת עורך מחסנים", "Warehouse editor save"))
        old = cat.set_index("sku").to_dict("index")
        page.conn.execute("DELETE FROM Catalog")
        for r in review["rows"]:
            sku = r["sku"]
            if not sku:
                continue
            tp = r["item_type"] or "RAW"
            value = float(r["stock_val"] or 0)
            weight = tp in WEIGHT_TYPES
            w_g = value * page.w_factor if weight else 0.0
            q_u = 0.0 if weight else value
            wh_key = "WH_RAW" if tp == "RAW" else ("WH_BULK" if tp == "BULK" else ("WH_PACK" if tp == "PKG" else "WH_FG"))
            prev = old.get(sku, {})
            page.conn.execute("""
                INSERT INTO Catalog (sku, name, item_type, qty_units, weight_grams, open_orders, stock_movements, main_supplier, alt_suppliers, last_stock_entry, primary_warehouse,
                                     item_price, min_order_qty, last_purchase_price, sap_code)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (sku, r["name"], tp, q_u, w_g, r["open_orders"] or "0", r["stock_movements"] or "-",
                  r["main_supplier"], r["alt_suppliers"], r["last_stock_entry"] or "-", wh_key,
                  float(prev.get("item_price", 0) or 0), float(prev.get("min_order_qty", 1) or 1),
                  float(prev.get("last_purchase_price", 0) or 0), str(prev.get("sap_code", "") or "")))
        page.conn.commit()
        page.inventory.reconcile_batches()
        page.clear_pending(PENDING_CATALOG)
        page.flash(page.L("המחסנים עודכנו בהצלחה!", "Warehouses updated."))
    elif action == "cancel":
        page.clear_pending(PENDING_CATALOG)


def _count_action(page: Page, action: str, cat: pd.DataFrame, wh: str, types: dict) -> None:
    if action == "review":
        df_wh = _subset(cat, wh)
        is_w = wh in ("RAW", "BULK", "COL")
        rows = _count_rows(page, df_wh, is_w)
        changed, invalid = _parse_count_post(page, page.request.POST, rows, is_w)
        if invalid:
            page.error(page.L("יש לתקן ערכי ספירה שליליים או ריקים.", "Fix blank or negative counted values."))
            return
        if not changed:
            page.error(page.L("אין שינויים לשמירה.", "No changes to save."))
            return
        page.set_pending(PENDING_COUNT, {"warehouse": wh, "rows": changed})
    elif action == "confirm":
        review = page.pending(PENDING_COUNT)
        if not review or not page.request.POST.get("confirmed"):
            page.error(page.L("יש לאשר את הפרשי הספירה לפני העדכון.", "Confirm the differences before updating."))
            return
        page.push_backup("stock", page.L("ספירת מחסן", "Warehouse count"))
        _apply_stock(page.conn, [{"sku": r["sku"], "counted": r["counted_base"]} for r in review["rows"]], types, page.inventory.reconcile_batches)
        page.clear_pending(PENDING_COUNT)
        page.flash(page.L(f"עודכנו {len(review['rows'])} פריטים לפי הספירה.", f"Updated {len(review['rows'])} items from the count."))
    elif action == "cancel":
        page.clear_pending(PENDING_COUNT)


def _import_action(page: Page, request, action: str, cat: pd.DataFrame, types: dict) -> None:
    if action == "upload":
        upload = request.FILES.get("file")
        if upload is None:
            page.error(page.L("לא נבחר קובץ.", "No file selected."))
            return
        try:
            df = read_table(upload.name, upload.read())
        except ValueError as exc:
            page.error(str(exc))
            return
        page.clear_pending(PENDING_IMPORT)
        page.set_pending(PENDING_IMPORT_FILE, {
            "filename": upload.name,
            "columns": list(df.columns),
            "records": df.astype(object).where(df.notna(), None).values.tolist(),
            "rows_read": len(df),
        })
    elif action == "map":
        file_info = page.pending(PENDING_IMPORT_FILE)
        if not file_info:
            page.error(page.L("טרם הועלה קובץ.", "No file uploaded yet."))
            return
        kind = request.POST.get("kind", "stock")
        unit = request.POST.get("unit", "kg")
        mapping = {"sku": request.POST.get("map_sku") or None, "qty": request.POST.get("map_qty") or None}
        if kind == "po":
            mapping["po_number"] = request.POST.get("map_po_number") or None
            mapping["supplier"] = request.POST.get("map_supplier") or None
            mapping["eta"] = request.POST.get("map_eta") or None
        required = ["sku", "qty"] + (["po_number"] if kind == "po" else [])
        if not all(mapping.get(k) for k in required):
            page.warn(page.L("יש למפות את כל השדות הנדרשים.", "Map all required fields."))
            return
        df = _import_table(file_info)
        page.set_pending(PENDING_IMPORT, _build_import(page, kind, mapping, unit, df, cat))
    elif action == "confirm":
        review = page.pending(PENDING_IMPORT)
        if not review or review["errors"] or not page.request.POST.get("confirmed"):
            page.error(page.L("יש לאשר את הייבוא ולתקן שגיאות לפני העדכון.", "Confirm the import and fix any errors before updating."))
            return
        page.push_backup("stock", page.L("ייבוא ERP", "ERP import"))
        if review["kind"] == "stock":
            _apply_stock(page.conn, review["rows"], types, page.inventory.reconcile_batches)
            message = page.L(f"עודכנו {len(review['rows'])} מק\"טים מקובץ ה-ERP.", f"Updated {len(review['rows'])} SKUs from the ERP file.")
        else:
            weight_skus = set(cat.loc[cat["item_type"].isin(WEIGHT_TYPES), "sku"].astype(str))
            for row in review["rows"]:
                is_w = row["sku"] in weight_skus
                existing = page.conn.execute("SELECT po_id FROM PurchaseOrders WHERE po_number = ?", (row["po_number"],)).fetchone()
                qty_units = 0.0 if is_w else row["qty_base"]
                qty_grams = row["qty_base"] if is_w else 0.0
                if existing:
                    page.conn.execute(
                        "UPDATE PurchaseOrders SET sku=?, supplier=?, order_qty_units=?, order_weight_grams=?, eta_date=? WHERE po_id=?",
                        (row["sku"], row["supplier"], qty_units, qty_grams, row["eta"], existing[0]),
                    )
                else:
                    page.conn.execute(
                        "INSERT INTO PurchaseOrders (po_number, sku, supplier, order_qty_units, order_weight_grams, eta_date, target_wh, status) "
                        "VALUES (?,?,?,?,?,?,?,?)",
                        (row["po_number"], row["sku"], row["supplier"], qty_units, qty_grams, row["eta"], "WH_RAW", "In Transit"),
                    )
            page.conn.commit()
            message = page.L(f"יובאו {len(review['rows'])} שורות הזמנה.", f"Imported {len(review['rows'])} order rows.")
        page.clear_pending(PENDING_IMPORT)
        page.clear_pending(PENDING_IMPORT_FILE)
        page.flash(message)
    elif action == "cancel":
        page.clear_pending(PENDING_IMPORT)
        page.clear_pending(PENDING_IMPORT_FILE)


def _summary(page: Page, cat: pd.DataFrame) -> list[dict]:
    """Top cards: warehouses in use, catalog SKUs, units on hand, and weight on hand."""
    L = page.L
    used = cat["primary_warehouse"].fillna("")
    warehouses = int(used[used != ""].nunique())
    total_units = float(cat["qty_units"].fillna(0).sum())
    total_weight = float(cat["weight_grams"].fillna(0).sum())
    return [
        {"label": L("מחסנים", "Warehouses"), "value": f"{warehouses:,}"},
        {"label": L("מקטים ייחודיים", "Unique SKUs"), "value": f"{len(cat):,}"},
        {"label": L('סה"כ יחידות', "Total units"), "value": f"{total_units:,.0f}"},
        {"label": L("סה\"כ משקל", "Total weight"), "value": page.fmt(total_weight, True)},
    ]


def _render(page: Page, request, wh: str, tab: str, query: str):
    L = page.L
    cat = pd.read_sql("SELECT * FROM Catalog", page.conn)
    df_wh = _subset(cat, wh)
    if wh == "BULK":
        # Bulk names start with "בלק" in the data; drop that prefix on this screen only.
        df_wh = df_wh.assign(name=df_wh["name"].astype(str).str.replace(r"^בלק\s+", "", regex=True))
    is_w = wh in ("RAW", "BULK", "COL")
    po_open = pd.read_sql(
        "SELECT * FROM PurchaseOrders WHERE status NOT IN ('Received','Cancelled') ORDER BY eta_date ASC", page.conn
    )
    data = {
        "summary": _summary(page, cat),
        "wh_options": [{"key": k, "label": v, "active": k == wh} for k, v in _warehouses(page)],
        "tabs": [
            {"key": k, "label": L(he, en), "active": k == tab, "url": f"?wh={wh}&tab={k}"}
            for k, he, en in TABS
        ],
        "tab": tab,
        "wh": wh,
        "is_w": is_w,
        "unit_label": page.w_label if is_w else page.u_label,
        "here": request.get_full_path().split("?")[0] + f"?wh={wh}&tab={tab}",
        "page_title": L("מחסנים (מלאי, תפוגה ורכש)", "Warehouses (stock, expiry & PO)"),
        "page_subtitle": L("ניהול המלאי בכל מחסן, ההזמנות הפתוחות והספקים.", "Manage stock in each warehouse, open purchase orders and suppliers."),
    }
    if tab == "stock":
        data["stock"] = _stock_tab(page, df_wh, is_w, query)
    elif tab == "po":
        data["po_rows"] = _po_tab(page, df_wh, is_w, po_open)
    elif tab == "sup":
        data["sup_rows"] = _sup_tab(df_wh)
    elif tab == "edit":
        review = page.pending(PENDING_CATALOG)
        if review:
            before = _catalog_rows_from_db(page, cat)
            columns = [
                "last_stock_entry", "alt_suppliers", "main_supplier", "stock_movements",
                "open_orders", "stock_val", "item_type", "name", "sku",
            ]
            data["catalog_review"] = _catalog_status(page, before, review["rows"], [], columns) | {"rows": review["rows"]}
        else:
            data["catalog_editable"] = _catalog_rows_from_db(page, cat) + [
                dict.fromkeys(CATALOG_FIELDS, "") for _ in range(NEW_ROWS)
            ]
        data["item_types"] = ITEM_TYPES
        data["po_statuses"] = PO_STATUSES
    elif tab == "count":
        rows = _count_rows(page, df_wh, is_w)
        data["count_rows"] = rows
        data["count_review"] = page.pending(PENDING_COUNT)
    elif tab == "import":
        data["import_file"] = page.pending(PENDING_IMPORT_FILE)
        data["import_review"] = page.pending(PENDING_IMPORT)
        if data["import_file"]:
            cols = [""] + data["import_file"]["columns"]
            data["import_columns"] = cols
            data["import_guess"] = {
                f: guess_column(data["import_file"]["columns"], f) or ""
                for f in ("sku", "qty", "po_number", "supplier", "eta")
            }
    return page.render("erp/inventory.html", **data)
