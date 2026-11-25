"""Batches and traceability: batch balances and expiry, manual receipts, and the forward/backward trace."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from cosmetics_erp.formatting import format_date
from cosmetics_erp.services.planning import PlanningService

from .page import Page

WEIGHT_TYPES = ("RAW", "BULK")
PENDING_RECEIPT = "manual_receipt"
TABS = ("stock", "receipt", "trace")


def _days_left(value, parse_date):
    parsed = parse_date(value)
    return (parsed - date.today()).days if parsed else None


def _stock_tab(page: Page, df_b: pd.DataFrame, params):
    L = page.L
    sku_filter = params.get("sku", "")
    show_depleted = bool(params.get("depleted"))
    search = params.get("q", "").strip()

    view = df_b.copy()
    if sku_filter:
        view = view[view["sku"] == sku_filter]
    if not show_depleted:
        view = view[view["status"] == "Active"]
    if search:
        cols = view[["sku", "name", "batch_no"]].fillna("").astype(str)
        view = view[cols.apply(lambda c: c.str.contains(search, case=False, regex=False)).any(axis=1)]
    view = view.assign(_noexp=view["expiry_date"].fillna("").eq("")).sort_values(["sku", "_noexp", "expiry_date", "batch_id"])

    rows = []
    for _, r in view.iterrows():
        is_w = r["item_type"] in WEIGHT_TYPES
        dl = r["days_left"]
        rows.append({
            "batch_no": r["batch_no"],
            "remaining": page.fmt(float(r["weight_grams"] if is_w else r["qty_units"]), is_w),
            "expiry": format_date(r["expiry_date"], is_he=page.is_he),
            "days_left": "-" if (dl is None or pd.isna(dl)) else str(int(dl)),
            "expired": dl is not None and not pd.isna(dl) and dl < 0,
            "status": L("פעילה", "Active") if r["status"] == "Active" else L("אזלה", "Depleted"),
            "source": r["source"],
            "received": format_date(r["received_date"], is_he=page.is_he),
            "name": r["name"],
            "sku": r["sku"],
        })
    skus = sorted(df_b["sku"].unique())
    return {
        "rows": rows,
        "skus": skus,
        "sku_filter": sku_filter,
        "show_depleted": show_depleted,
        "search": search,
        "shown": len(rows),
    }


def _receipt_tab(page: Page, request, post):
    L = page.L
    catalog = pd.read_sql("SELECT sku, name, item_type FROM Catalog ORDER BY sku", page.conn)
    review = page.pending(PENDING_RECEIPT)
    selected = (post or {}).get("sku") or request.GET.get("sku") or catalog["sku"].iloc[0]
    sel = catalog[catalog["sku"] == selected]
    if sel.empty:
        selected = catalog["sku"].iloc[0]
        sel = catalog[catalog["sku"] == selected]
    is_w = sel.iloc[0]["item_type"] in WEIGHT_TYPES
    default_batch = page.inventory.gen_batch_no(selected)
    return {
        "catalog": catalog.to_dict("records"),
        "selected": selected,
        "is_w": is_w,
        "unit_label": page.w_label if is_w else page.u_label,
        "default_batch": default_batch,
        "default_expiry": (date.today() + timedelta(days=365)).isoformat(),
        "no_expiry_default": sel.iloc[0]["item_type"] == "PKG",
        "review": review,
    }


def _receipt_action(page: Page, post) -> None:
    L = page.L
    sku = post.get("sku", "")
    cat = page.conn.execute("SELECT item_type FROM Catalog WHERE sku=?", (sku,)).fetchone()
    if not cat:
        page.error(L("מק\"ט לא קיים בקטלוג.", "SKU not found in the catalog."))
        return
    is_w = cat[0] in WEIGHT_TYPES
    try:
        amount = float(post.get("amount", "0").replace(",", "."))
    except ValueError:
        amount = 0.0
    if amount <= 0:
        page.error(L("הכמות חייבת להיות גדולה מאפס.", "The quantity must be greater than zero."))
        return
    base_amount = amount * page.w_factor if is_w else amount
    batch = post.get("batch", "").strip() or page.inventory.gen_batch_no(sku)
    no_expiry = bool(post.get("no_expiry"))
    expiry = "" if no_expiry else post.get("expiry", "")
    if not no_expiry:
        try:
            date.fromisoformat(expiry)
        except ValueError:
            page.error(L("יש להזין תאריך תפוגה תקין.", "Enter a valid expiry date."))
            return
    page.set_pending(PENDING_RECEIPT, {
        "sku": sku, "batch": batch, "expiry": expiry, "amount_base": base_amount,
        "is_weight": is_w, "amount_text": page.fmt(base_amount, is_w),
    })


def _receipt_confirm(page: Page, post) -> None:
    L = page.L
    review = page.pending(PENDING_RECEIPT)
    if not review or not post.get("confirmed"):
        page.error(L("יש לאשר את הכניסה לפני העדכון.", "Confirm the receipt before updating stock."))
        return
    if page.batch_exists(review["sku"], review["batch"]):
        page.error(L(f"אצווה {review['batch']} כבר קיימת למק\"ט {review['sku']}. בחר/י מספר אצווה אחר.",
                     f"Batch {review['batch']} already exists for SKU {review['sku']}. Choose another batch number."))
        return
    page.push_backup("stock", f"{L('כניסת מלאי', 'Receipt')} {review['sku']}")
    page.inventory.add_batch(review["sku"], review["batch"], review["amount_base"], review["is_weight"], review["expiry"], "MANUAL")
    stamp = datetime.now().strftime("%Y-%m-%d")
    if review["is_weight"]:
        page.conn.execute("UPDATE Catalog SET weight_grams = weight_grams + ?, last_stock_entry = ? WHERE sku=?",
                          (review["amount_base"], f"{stamp} (+{review['amount_base'] / 1000:.2f} ק\"ג)", review["sku"]))
    else:
        page.conn.execute("UPDATE Catalog SET qty_units = qty_units + ?, last_stock_entry = ? WHERE sku=?",
                          (review["amount_base"], f"{stamp} (+{review['amount_base']:.0f} יח')", review["sku"]))
    page.conn.commit()
    page.clear_pending(PENDING_RECEIPT)
    page.flash(L(f"נוספה אצווה {review['batch']} למק\"ט {review['sku']}.", f"Added batch {review['batch']} to SKU {review['sku']}."))


def _trace_tab(page: Page, request, df_b: pd.DataFrame):
    skus = sorted(df_b["sku"].unique())
    if not skus:
        return {"skus": [], "back": [], "fwd": []}
    sku = request.GET.get("sku") or skus[0]
    if sku not in skus:
        sku = skus[0]
    batches = list(df_b[df_b["sku"] == sku]["batch_no"])
    batch = request.GET.get("batch") or batches[0]
    if batch not in batches:
        batch = batches[0]
    names = pd.read_sql("SELECT sku, name, item_type FROM Catalog", page.conn).set_index("sku")

    def rows_for(direction):
        out = []
        for level, s, b, qu, wg, when, ref in page.inventory.trace_chain(sku, batch, direction):
            is_w = (names.loc[s]["item_type"] in WEIGHT_TYPES) if s in names.index else False
            out.append({
                "level": level,
                "batch_no": b,
                "qty": page.fmt(float(wg if is_w else qu), is_w),
                "date": format_date(when, is_he=page.is_he),
                "reference": ref,
                "name": names.loc[s]["name"] if s in names.index else "?",
                "sku": s,
            })
        return out

    return {
        "skus": skus,
        "batches": batches,
        "sku": sku,
        "batch": batch,
        "back": rows_for("back"),
        "fwd": rows_for("fwd"),
    }


@login_required
def batches(request):
    if request.method == "POST":
        with Page(request, "batches", edit=True) as page:
            action = request.POST.get("action", "")
            if action == "review":
                _receipt_action(page, request.POST)
            elif action == "confirm":
                _receipt_confirm(page, request.POST)
            elif action == "cancel":
                page.clear_pending(PENDING_RECEIPT)
            return redirect(f"/batches/?tab=receipt")

    with Page(request, "batches") as page:
        L = page.L
        tab = request.GET.get("tab", "stock")
        if tab not in TABS:
            tab = "stock"
        df_b = pd.read_sql("SELECT b.*, c.name, c.item_type FROM Batches b JOIN Catalog c ON b.sku = c.sku", page.conn)
        parse_date = PlanningService.parse_date
        if not df_b.empty:
            df_b["days_left"] = df_b["expiry_date"].apply(lambda v: _days_left(v, parse_date))
            active = df_b[df_b["status"] == "Active"]
        else:
            df_b["days_left"] = pd.Series(dtype=float)
            active = df_b
        n_active = len(active)
        n_expired = int((active["days_left"] < 0).sum()) if n_active else 0
        n_soon = int(((active["days_left"] >= 0) & (active["days_left"] <= 30)).sum()) if n_active else 0

        data = {
            "tab": tab,
            "tabs": [
                {"key": "stock", "label": L("מלאי לפי אצווה (FEFO)", "Stock by batch (FEFO)")},
                {"key": "receipt", "label": L("כניסת מלאי ידנית עם אצווה", "Manual receipt with batch")},
                {"key": "trace", "label": L("עקיבות (Traceability)", "Traceability")},
            ],
            "metrics": [
                (L("אצוות פעילות", "Active batches"), n_active),
                (L("פגות תוקף תוך 30 יום", "Expiring within 30 days"), n_soon),
                (L("פגות תוקף (חסומות לשימוש)", "Expired (blocked)"), n_expired),
            ],
            "has_batches": not df_b.empty,
            "undo_available": page.last_backup("stock") is not None,
            "undo_info": page.last_backup("stock"),
        }
        if tab == "stock":
            data["stock"] = _stock_tab(page, df_b, request.GET) if not df_b.empty else {"rows": [], "skus": []}
        elif tab == "receipt":
            data["receipt"] = _receipt_tab(page, request, None)
        else:
            data["trace"] = _trace_tab(page, request, df_b)
        return page.render(
            "erp/batches.html",
            title=L("מרשם אצוות ועקיבות (FEFO)", "Batches & traceability (FEFO)"),
            subtitle=L("בדוק/י יתרות אצוות ותפוגה, הוסף/י כניסה ידנית ובדוק/י את עקיבות האצוות.",
                       "Review batch balances and expiry, add manual receipts, and inspect batch consumption links."),
            **data,
        )
