"""Planning and production: product trees (BOM), the production and packaging simulators,
the weekly plan, and the master work simulator.

The simulators show the week-by-week stock picture. The numbers come from
``cosmetics_erp.services``; the views only arrange them for the templates.
"""
from __future__ import annotations

import csv
from datetime import date, datetime, timedelta

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse

from cosmetics_erp.services.bom import PARENT_TYPES, allowed_component_types, to_bom_rows, validate_bom
from cosmetics_erp.services.manufacturing import plan_components, post_run
from cosmetics_erp.services.master_work import simulate_master_work
from cosmetics_erp.services.where_used import WEEKS, compute_where_used

from .page import Page

WEEK_COLS = WEEKS
PENDING_SCHEDULE = "schedule"
BOM_NEW_ROWS = 3


# Weekly plan

def _ensure_schedule_rows(conn, skus: list[str]) -> None:
    for sku in skus:
        conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (sku,))
    conn.commit()


def _schedule_frame(conn, item_type: str) -> pd.DataFrame:
    return pd.read_sql(f"""
        SELECT c.sku || ' - ' || c.name AS parent_label, c.sku, c.name AS parent_name,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM WeeklySchedule s
        JOIN Catalog c ON s.parent_sku = c.sku
        WHERE c.item_type = '{item_type}'
        ORDER BY c.sku
    """, conn)


def _bom_frame(conn, parent_type: str, comp_types: tuple[str, ...]) -> pd.DataFrame:
    placeholders = ",".join("?" * len(comp_types))
    return pd.read_sql(f"""
        SELECT b.component_sku, c.name AS comp_name, c.item_type AS comp_type,
               b.parent_sku, p.name AS parent_name,
               b.req_qty_units, b.req_weight_grams,
               c.qty_units AS avail_units, c.weight_grams AS avail_grams,
               s.W1, s.W2, s.W3, s.W4, s.W5, s.W6, s.W7, s.W8
        FROM BOM b
        JOIN Catalog p ON b.parent_sku = p.sku
        JOIN Catalog c ON b.component_sku = c.sku
        JOIN WeeklySchedule s ON b.parent_sku = s.parent_sku
        WHERE p.item_type = ? AND c.item_type IN ({placeholders})
        ORDER BY CASE WHEN c.item_type = 'BULK' THEN 0 ELSE 1 END, b.component_sku, b.parent_sku
    """, conn, params=(parent_type, *comp_types))


def _schedule_post(page: Page, post, sched: pd.DataFrame, pending_name: str) -> None:
    """Handle the full weekly-table review and confirm steps."""
    L = page.L
    action = post.get("action")
    if action == "sched_review":
        rows, invalid = [], False
        for i, r in enumerate(sched.to_dict("records")):
            values = {}
            for w in WEEK_COLS:
                try:
                    v = float(post.get(f"{w}_{i}", "").replace(",", "."))
                except ValueError:
                    v, invalid = None, True
                    break
                if v < 0:
                    invalid = True
                values[w] = v
            if invalid:
                break
            if any(abs(values[w] - float(r[w] or 0)) > 1e-6 for w in WEEK_COLS):
                rows.append({"sku": r["sku"], "parent_label": r["parent_label"], **values})
        if invalid:
            page.error(L("הכמויות חייבות להיות מספרים שאינם שליליים.", "Quantities must be valid non-negative numbers."))
            return
        if not rows:
            page.error(L("אין שינויים לשמירה.", "No changes to save."))
            return
        page.set_pending(pending_name, rows)
    elif action == "sched_confirm":
        rows = page.pending(pending_name)
        if not rows or not post.get("confirmed"):
            page.error(L("יש לאשר את השינויים לפני השמירה.", "Confirm the changes before saving."))
            return
        page.push_backup("schedule", L("שמירת תוכנית שבועות", "Weekly plan save"))
        for r in rows:
            page.conn.execute(
                "UPDATE WeeklySchedule SET W1=?,W2=?,W3=?,W4=?,W5=?,W6=?,W7=?,W8=? WHERE parent_sku=?",
                (*[r[w] for w in WEEK_COLS], r["sku"]),
            )
        page.conn.commit()
        page.clear_pending(pending_name)
        page.flash(L("התוכנית השבועית נשמרה.", "Weekly plan saved."))
    elif action == "sched_cancel":
        page.clear_pending(pending_name)


def _plan_quick(page: Page, post) -> None:
    """Quick planner: set one parent's quantity for one week (backed up, so it can be undone)."""
    L = page.L
    sku = post.get("plan_sku", "")
    week = post.get("plan_week", "")
    if week not in WEEK_COLS:
        page.error(L("בחר/י שבוע תקין.", "Choose a valid week."))
        return
    try:
        qty = float(post.get("plan_qty", "0").replace(",", "."))
    except ValueError:
        qty = -1
    if qty < 0:
        page.error(L("הכמות חייבת להיות מספר שאינו שלילי.", "The quantity must be a non-negative number."))
        return
    page.push_backup("schedule", f"{L('תכנון', 'Plan')} {sku} {week}")
    page.conn.execute(f"UPDATE WeeklySchedule SET {week} = ? WHERE parent_sku = ?", (qty, sku))
    page.conn.commit()
    page.flash(L(f"התכנון עודכן: {sku} · {week} = {qty:g}.", f"Plan updated: {sku} · {week} = {qty:g}."))


def _planner_context(page: Page, sched: pd.DataFrame, unit_label: str):
    options = []
    for r in sched.itertuples():
        options.append({"sku": r.sku, "label": r.parent_label})
    return {
        "options": options,
        "weeks": [{"code": p[0], "label": p[2]} for p in page.periods],
        "unit_label": unit_label,
    }


def _weekly_table(sched: pd.DataFrame, unit_label: str):
    rows = []
    for i, r in enumerate(sched.to_dict("records")):
        weeks = {w: r[w] for w in WEEK_COLS}
        rows.append({
            "index": i,
            "sku": r["sku"],
            "label": r["parent_label"],
            "weeks": [{"code": w, "value": int(float(weeks[w] or 0))} for w in WEEK_COLS],
            "total": int(sum(float(weeks[w] or 0) for w in WEEK_COLS)),
        })
    return rows


def _month_groups(periods) -> list[dict]:
    """Consecutive weeks that share a month, for the two-level header."""
    groups: list[dict] = []
    for p in periods:
        if groups and groups[-1]["label"] == p[1]:
            groups[-1]["span"] += 1
        else:
            groups.append({"label": p[1], "span": 1})
    return groups


def _where_used(page: Page, sched: pd.DataFrame, bom: pd.DataFrame, parent_unit: str, search: str, child: str, parent: str):
    """Component table: balances week by week, with the incoming POs in each week."""
    incoming = page.inventory.get_incoming_map()
    supplier_of = dict(page.conn.execute("SELECT sku, main_supplier FROM Catalog").fetchall())
    alt_of: dict[str, list[str]] = {}
    for sku, alt_sku in page.conn.execute("SELECT sku, alt_sku FROM AltSkus ORDER BY sku, priority").fetchall():
        alt_of.setdefault(sku, []).append(alt_sku)
    alt_of = {k: ", ".join(v) for k, v in alt_of.items()}
    bom_records = bom.to_dict("records")
    result = compute_where_used(bom_records, incoming)
    cells = result["cells"]
    final = result["final"]

    # Filters: child SKU, linked parent, and free text over both.
    keep = []
    for idx, r in enumerate(bom_records):
        if child and r["component_sku"] != child:
            continue
        if parent and r["parent_sku"] != parent:
            continue
        if search:
            hay = " ".join(str(r.get(k, "")) for k in ("component_sku", "comp_name", "parent_sku", "parent_name")).casefold()
            if search.casefold() not in hay:
                continue
        keep.append(idx)

    shared_count: dict[str, int] = {}
    for r in bom_records:
        shared_count[r["component_sku"]] = shared_count.get(r["component_sku"], 0) + 1

    lines = []
    seen_child: set[str] = set()
    comp_used: dict[str, list[float]] = {}
    comp_is_w: dict[str, bool] = {}
    for idx in keep:
        r = bom_records[idx]
        comp = r["component_sku"]
        is_w = r["comp_type"] in ("RAW", "BULK")
        per_unit = float(r["req_weight_grams"] if is_w else r["req_qty_units"])
        per_unit_text = f"{per_unit:g} {'גרם' if page.is_he else 'g'}" if (r["comp_type"] == "BULK" and per_unit < 1000) else page.fmt(per_unit, is_w)
        first = comp not in seen_child
        seen_child.add(comp)
        stock0 = float(r["avail_grams"] if is_w else r["avail_units"])
        final_cell = final[comp]
        comp_is_w[comp] = is_w
        comp_used.setdefault(comp, [0.0] * len(cells[idx]))
        week_cells = []
        for w_idx, cell in enumerate(cells[idx]):
            comp_used[comp][w_idx] += float(cell["used"] or 0.0)
            week_cells.append({
                "value": page.fmt(cell["after"], is_w),
                "is_ok": cell["is_ok"],
                "parent": r["parent_sku"],
                "component": comp,
                "week_title": page.periods[w_idx][2],
                "planned": int(float(r[WEEK_COLS[w_idx]] or 0)),
                "before": page.fmt(cell["before"], is_w),
                "used": page.fmt(cell["used"], is_w),
                "used_raw": float(cell["used"] or 0.0),
                "total_used": page.fmt(cell["tot_used_all"], is_w),
                "after": page.fmt(cell["after"], is_w),
                "incoming": None if not cell["incoming"] else {
                    "amount": "+" + page.fmt(cell["incoming"]["amt"], is_w),
                    "pos": ", ".join(cell["incoming"]["pos"]),
                },
                "shared": shared_count[comp] > 1,
            })
        source = (
            page.L("ממחסן בלקים (במשקל)", "From bulks WH") if r["comp_type"] == "BULK"
            else page.L("ממחסן אריזות (ביח')", "From packaging WH") if r["comp_type"] == "PKG"
            else page.L("ממחסן חומר גלם", "From raw WH")
        )
        lines.append({
            "span": len([i for i in keep if bom_records[i]["component_sku"] == comp]) if first else 0,
            "first": first,
            "component_sku": comp,
            "component_name": r["comp_name"],
            "source": source,
            "shared": shared_count[comp] > 1,
            "shared_count": shared_count[comp],
            "parent_sku": r["parent_sku"],
            "parent_name": r["parent_name"],
            "per_unit": per_unit_text,
            "stock": page.fmt(stock0, is_w),
            "final": page.fmt(final_cell["after"], is_w),
            "final_ok": final_cell["is_ok"],
            "weeks": week_cells,
            "supplier": supplier_of.get(comp) or "",
            "alt": alt_of.get(comp, ""),
            "status_label": page.L("מוכן", "Ready") if final_cell["is_ok"] else page.L("חסר", "Short"),
            "status_css": "pill-closed" if final_cell["is_ok"] else "pill-bad",
        })
    # One row per component. Its balance is the balance after every product that uses it;
    # the open cell lists what each product takes that week.
    by_comp: dict[str, list[dict]] = {}
    for line in lines:
        by_comp.setdefault(line["component_sku"], []).append(line)
    merged: list[dict] = []
    for comp, members in by_comp.items():
        is_w = comp_is_w[comp]
        last = members[-1]
        weeks_out = []
        for w_idx, last_cell in enumerate(last["weeks"]):
            first_cell = members[0]["weeks"][w_idx]
            used_total = sum(m["weeks"][w_idx]["used_raw"] for m in members)
            incoming = next((m["weeks"][w_idx]["incoming"] for m in members if m["weeks"][w_idx]["incoming"]), None)
            weeks_out.append({
                "value": last_cell["value"],
                "is_ok": last_cell["is_ok"],
                "incoming": incoming,
                "week_title": last_cell["week_title"],
                "before": first_cell["before"],
                "after": last_cell["after"],
                "used_total": page.fmt(used_total, is_w),
                "breakdown": [{"parent": m["parent_sku"], "used": m["weeks"][w_idx]["used"]} for m in members],
            })
        eight_week_total = sum(m["weeks"][w]["used_raw"] for m in members for w in range(len(last["weeks"])))
        merged.append({
            "first": True,
            "span": 1,
            "component_sku": comp,
            "component_name": members[0]["component_name"],
            "source": members[0]["source"],
            "parents": [{"sku": m["parent_sku"], "per": m["per_unit"]} for m in members],
            "products_total": page.fmt(eight_week_total, is_w),
            "supplier": members[0]["supplier"],
            "stock": members[0]["stock"],
            "final": last["final"],
            "final_ok": last["final_ok"],
            "status_label": last["status_label"],
            "status_css": last["status_css"],
            "alt": members[0]["alt"],
            "weeks": weeks_out,
        })
    lines = merged
    return {"lines": lines, "parent_unit": parent_unit, "shown": len(keep), "total": len(bom_records)}


def _sched_rows_for_display(sched: pd.DataFrame, parent_unit: str):
    rows = []
    for r in sched.to_dict("records"):
        weeks = [int(float(r[w] or 0)) for w in WEEK_COLS]
        rows.append({
            "label": r["parent_label"],
            "weeks": [{"value": v, "unit": parent_unit} for v in weeks],
            "total": f"{sum(weeks):,} {parent_unit}",
        })
    return rows


def _review_rows(rows):
    """Changed schedule rows in the shape the template shows them."""
    if not rows:
        return None
    return [
        {"label": r["parent_label"], "weeks": [{"code": w, "value": r[w]} for w in WEEK_COLS]}
        for r in rows
    ]


def _parse_int(value: str, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


# Production and packaging runs

def _production_run(page: Page, post) -> None:
    L = page.L
    bulk = post.get("bulk_sku", "")
    try:
        kg = float(post.get("kg", "0").replace(",", "."))
    except ValueError:
        kg = 0.0
    if kg < 1:
        page.error(L("הכמות חייבת להיות לפחות 1 ק\"ג.", "The quantity must be at least 1 kg."))
        return
    try:
        expiry = date.fromisoformat(post.get("expiry", ""))
    except ValueError:
        page.error(L("יש להזין תאריך תפוגה תקין.", "Enter a valid expiry date."))
        return
    if expiry < date.today():
        page.error(L("תאריך התפוגה חייב להיות היום או בעתיד.", "The expiry date must be today or later."))
        return
    bom_rows = page.conn.execute("SELECT component_sku, req_weight_grams FROM BOM WHERE parent_sku = ?", (bulk,)).fetchall()
    components = [
        {"sku": c, "need": float(w or 0) * kg, "is_weight": True, "from_wh": "WH_RAW"}
        for c, w in bom_rows
    ]
    plans, shortages = plan_components(page.inventory, components)
    errors = [
        f"{s['sku']}: " + L(f"חסרים {s['short'] / 1000:.2f} ק\"ג במלאי תקף (לא פג תוקף)",
                           f"short {s['short'] / 1000:.2f} kg of valid stock (not expired)")
        for s in shortages
    ]
    batch = post.get("batch", "").strip() or page.inventory.gen_batch_no(bulk)
    if page.batch_exists(bulk, batch):
        errors.append(L(f"אצווה {batch} כבר קיימת למק\"ט {bulk}. בחר/י מספר אצווה אחר.",
                        f"Batch {batch} already exists for SKU {bulk}. Choose another batch number."))
    if errors:
        for e in errors:
            page.error(e)
        page.error(L("לא ניתן לייצר – אין מספיק חומר גלם תקף.", "Cannot produce – not enough valid raw material."))
        return
    page.push_backup("stock", f"{L('ייצור בלק', 'Bulk production')} {bulk} ({kg:g} {L('ק\"ג', 'kg')})")
    result = post_run(
        page.conn, page.inventory, kind="production", parent_sku=bulk, batch_no=batch, plans=plans,
        expiry=expiry.strftime("%Y-%m-%d"), output_amount=kg * 1000.0, output_is_weight=True,
        now_d=datetime.now().strftime("%Y-%m-%d"), kg_display=kg,
    )
    msg = L(f"יוצרו {kg:g} ק\"ג של בלק {bulk} באצווה {batch} (תפוגה {result['expiry']}). חומרי הגלם נגרעו לפי FEFO והבלק הועבר למחסן בלקים.",
            f"Produced {kg:g} kg of bulk {bulk} in batch {batch} (expiry {result['expiry']}). Raw materials were consumed by FEFO and the bulk moved to the bulk warehouse.")
    if result["capped"]:
        msg += L(f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של חומר הגלם ({result['limiting']}).",
                 f" Note: the expiry was capped at the earliest raw-material expiry ({result['limiting']}).")
    page.flash(msg)


def _packaging_run(page: Page, post) -> None:
    L = page.L
    fg = post.get("fg_sku", "")
    try:
        units = int(float(post.get("units", "0")))
    except ValueError:
        units = 0
    if units < 1:
        page.error(L("הכמות חייבת להיות לפחות יחידה אחת.", "The quantity must be at least one unit."))
        return
    try:
        expiry = date.fromisoformat(post.get("expiry", ""))
    except ValueError:
        page.error(L("יש להזין תאריך תפוגה תקין.", "Enter a valid expiry date."))
        return
    if expiry < date.today():
        page.error(L("תאריך התפוגה חייב להיות היום או בעתיד.", "The expiry date must be today or later."))
        return
    bom_p = page.conn.execute("SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ?", (fg,)).fetchall()
    components = []
    for comp, comp_type, qty, grams in bom_p:
        is_w = comp_type == "BULK"
        per_unit = float(grams or 0) if is_w else float(qty or 0)
        components.append({
            "sku": comp,
            "need": per_unit * units,
            "is_weight": is_w,
            "from_wh": "WH_BULK" if is_w else "WH_PACK",
        })
    plans, shortages = plan_components(page.inventory, components)
    errors = []
    for s in shortages:
        short_text = f"{s['short'] / 1000:.2f} ק\"ג" if s["is_weight"] else f"{s['short']:.0f} יח'"
        errors.append(f"{s['sku']}: " + L(f"חסרים {short_text} במלאי תקף (לא פג תוקף)", f"short {short_text} of valid stock (not expired)"))
    batch = post.get("batch", "").strip() or page.inventory.gen_batch_no(fg)
    if page.batch_exists(fg, batch):
        errors.append(L(f"אצווה {batch} כבר קיימת למוצר {fg}. בחר/י מספר אצווה אחר.",
                        f"Batch {batch} already exists for product {fg}. Choose another batch number."))
    if errors:
        for e in errors:
            page.error(e)
        page.error(L("לא ניתן לבצע אריזה – אין מספיק רכיבים תקפים.", "Cannot pack – not enough valid components."))
        return
    page.push_backup("stock", f"{L('אריזת', 'Packing')} {fg} ({units} {page.u_label})")
    result = post_run(
        page.conn, page.inventory, kind="packaging", parent_sku=fg, batch_no=batch, plans=plans,
        expiry=expiry.strftime("%Y-%m-%d"), output_amount=float(units), output_is_weight=False,
        now_d=datetime.now().strftime("%Y-%m-%d"),
    )
    msg = L(f"נארזו {units} יח' של {fg} באצווה {batch} (תפוגה {result['expiry']}). המלאי נגרע ממחסן הבלקים וממחסן האריזות לפי FEFO.",
            f"Packed {units} units of {fg} in batch {batch} (expiry {result['expiry']}). Stock was consumed from the bulk and packaging warehouses by FEFO.")
    if result["capped"]:
        msg += L(f" שים לב: התפוגה הוגבלה לתפוגה המוקדמת ביותר של הרכיבים ({result['limiting']}).",
                 f" Note: the expiry was capped at the earliest component expiry ({result['limiting']}).")
    page.flash(msg)


def _run_context(page: Page, kind: str):
    today = date.today()
    if kind == "production":
        products = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'BULK' ORDER BY sku", page.conn)
        return {
            "products": products.to_dict("records"),
            "default_expiry": (today + timedelta(days=180)).isoformat(),
        }
    products = pd.read_sql("SELECT sku, name FROM Catalog WHERE item_type = 'FG' ORDER BY sku", page.conn)
    return {
        "products": products.to_dict("records"),
        "default_expiry": (today + timedelta(days=730)).isoformat(),
    }


def _simulator(request, screen: str, kind: str):
    """Shared view for the production and packaging simulators."""
    with Page(request, screen, edit=request.method == "POST") as page:
        if request.method == "POST":
            action = request.POST.get("action", "")
            if action.startswith("sched_"):
                _schedule_post(page, request.POST, _schedule_frame(page.conn, "BULK" if kind == "production" else "FG"), f"{PENDING_SCHEDULE}_{screen}")
            elif action == "plan":
                _plan_quick(page, request.POST)
            elif action == "run" and kind == "production":
                _production_run(page, request.POST)
            elif action == "run" and kind == "packaging":
                _packaging_run(page, request.POST)
            return redirect(request.get_full_path())
        return _simulator_get(page, request, screen, kind)


def _where_used_csv(where_used: dict, screen: str):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{screen}-components.csv"'
    writer = csv.writer(response)
    writer.writerow(["Component", "Parent", "Supplier", "Per 1", "Stock", "Cum. balance", "Status"])
    for line in where_used["lines"]:
        writer.writerow([line["component_sku"], ", ".join(p["sku"] for p in line["parents"]), line["supplier"],
                         "; ".join(f'{p["sku"]} {p["per"]}' for p in line["parents"]),
                         line["stock"], line["final"], line["status_label"]])
    return response


def _simulator_get(page: Page, request, screen: str, kind: str):
    L = page.L
    if kind == "production":
        parent_type, comp_types = "BULK", ("RAW",)
        parent_unit = "ק\"ג בלק" if page.is_he else "kg Bulk"
        title = L("1. סימולטור קו ייצור", "1. Production line simulator")
        subtitle = L(
            "קבע כמה ק\"ג בלק את/ה מתכנן/ת לייצר ולמתי – המערכת בודקת את מחסן חומרי הגלם (RAW) ומראה מתי יהיה חוסר.",
            "Set how many kg of bulk to make and when – the system checks the raw material warehouse (RAW) and shows when shortages occur.",
        )
    else:
        parent_type, comp_types = "FG", ("BULK", "PKG")
        parent_unit = page.u_label
        title = L("2. סימולטור אריזה", "2. Packaging simulator")
        subtitle = L(
            "קבע כמה יחידות מוצר סופי לארוז ולמתי – המערכת בודקת במקביל את מחסן הבלקים (BULK) ואת מחסן האריזות (PKG).",
            "Set how many finished units to pack and when – the system checks the bulk (BULK) and packaging (PKG) warehouses together.",
        )
    catalog_parents = pd.read_sql("SELECT sku FROM Catalog WHERE item_type = ?", page.conn, params=(parent_type,))
    _ensure_schedule_rows(page.conn, list(catalog_parents["sku"]))
    sched = _schedule_frame(page.conn, parent_type)
    bom = _bom_frame(page.conn, parent_type, comp_types)

    view = request.GET.get("view", "all")
    if kind == "packaging":
        if view == "bulk":
            bom = bom[bom["comp_type"] == "BULK"]
        elif view == "pkg":
            bom = bom[bom["comp_type"] == "PKG"]
    child = request.GET.get("child", "")
    parent = request.GET.get("parent", "")
    search = request.GET.get("q", "").strip()

    sched_for_planner = sched.copy()
    schedule_review = page.pending(f"{PENDING_SCHEDULE}_{screen}")
    wu = _where_used(page, sched, bom, page.u_label if kind == "packaging" else parent_unit, search, child, parent)
    if request.GET.get("export") == "csv":
        return _where_used_csv(wu, screen)
    return page.render(
        "erp/simulator.html",
        title=title,
        subtitle=subtitle,
        screen_key=screen,
        kind=kind,
        planner=_planner_context(page, sched_for_planner, parent_unit),
        weekly_table=_weekly_table(sched, parent_unit),
        schedule_review=_review_rows(schedule_review),
        where_used=wu,
        month_groups=_month_groups(page.periods),
        weeks=[{"code": p[0], "month": p[1], "label": p[2]} for p in page.periods],
        filter_children=[{"sku": s, "label": f"{s} - {n}"} for s, n in bom.drop_duplicates("component_sku")[["component_sku", "comp_name"]].values],
        filter_parents=[{"sku": s, "label": f"{s} - {n}"} for s, n in sched[["sku", "parent_name"]].drop_duplicates().values],
        view=view,
        child=child,
        parent=parent,
        q=search,
        runs=_run_context(page, kind),
        parent_unit=parent_unit,
        undo_info=page.last_backup("schedule"),
        stock_undo_info=page.last_backup("stock"),
        screen_name=screen,
        here=request.get_full_path(),
    )


@login_required
def production_planning(request):
    """One page for all production planning. ?view= picks the tab: production, packaging or master_work."""
    if not request.user.has_perm("erp.view_production_planning"):
        raise PermissionDenied
    handlers = {"production": production, "packaging": packaging, "master_work": master_work}
    view = request.GET.get("view", "production")
    return handlers.get(view, production)(request)


@login_required
def production(request):
    return _simulator(request, "production", "production")


@login_required
def packaging(request):
    return _simulator(request, "packaging", "packaging")


@login_required
def master_work(request):
    if request.method == "POST":
        with Page(request, "master_work", edit=True) as page:
            action = request.POST.get("action", "")
            if action.startswith("sched_"):
                _schedule_post(page, request.POST, _schedule_frame(page.conn, "FG"), f"{PENDING_SCHEDULE}_master_work")
            elif action == "plan":
                _plan_quick(page, request.POST)
            return redirect("master_work")

    with Page(request, "master_work") as page:
        L = page.L
        fg = pd.read_sql("SELECT sku FROM Catalog WHERE item_type = 'FG'", page.conn)
        _ensure_schedule_rows(page.conn, list(fg["sku"]))
        sched = _schedule_frame(page.conn, "FG")
        catalog = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams FROM Catalog", page.conn)
        bom = pd.read_sql("SELECT * FROM BOM", page.conn)
        incoming = page.inventory.get_incoming_map()
        cells = simulate_master_work(catalog, bom, sched.to_dict("records"), incoming, page.fmt)

        rows = []
        for r in sched.to_dict("records"):
            week_cells = []
            total_plan = total_make = 0
            for w_idx, w in enumerate(WEEK_COLS):
                cell = cells[(r["sku"], w)]
                total_plan += cell["planned"]
                total_make += cell["makeable"]
                week_cells.append({
                    "planned": cell["planned"],
                    "makeable": cell["makeable"],
                    "missing": cell["missing"],
                    "is_ok": cell["is_ok"],
                    "title": page.periods[w_idx][2],
                    "shortages": cell["shortages"],
                    "arrivals": cell["arrivals"],
                    "shortage_texts": [
                        {"label": s["kind"], "sku": s["sku"], "name": s["name"], "value": page.fmt(s["after"], s["is_weight"])}
                        for s in cell["shortages"]
                    ],
                })
            rows.append({
                "sku": r["sku"],
                "label": r["parent_label"],
                "weeks": week_cells,
                "total_plan": total_plan,
                "total_make": total_make,
                "total_ok": total_make >= total_plan,
            })
        return page.render(
            "erp/master_work.html",
            title=L("3. סימולטור עבודה מסכם", "3. Master work simulator"),
            subtitle=L(
                "לכל מק\"ט אב מוצג כמה יחידות מתוכנן לייצר בכל שבוע, כמה אפשר להכין בפועל, ומתי יווצר חוסר. לחץ על תא שבועי כדי לראות מה חסר.",
                "For each parent SKU: planned units per week, how many can actually be made, and when shortages occur. Open a weekly cell to see what is missing.",
            ),
            planner=_planner_context(page, sched, page.u_label),
            weeks=[{"code": p[0], "month": p[1], "label": p[2]} for p in page.periods],
            rows=rows,
            schedule_review=_review_rows(page.pending(f"{PENDING_SCHEDULE}_master_work")),
            u_label=page.u_label,
        )


# Product trees

def _bom_rows_from_post(post) -> list[dict]:
    rows = []
    for i in range(_parse_int(post.get("row_count", "0"), 0)):
        comp = post.get(f"comp_{i}", "").strip()
        qty_text = post.get(f"qty_{i}", "").strip()
        if not comp and not qty_text:
            continue
        try:
            qty = float(qty_text.replace(",", "."))
        except ValueError:
            qty = None
        rows.append({"component_sku": comp, "quantity": qty})
    return rows


@login_required
def bom(request):
    if request.method == "POST":
        with Page(request, "bom", edit=True) as page:
            return _bom_save(page, request)
    mode = request.GET.get("mode", "list")
    if mode == "list":
        with Page(request, "bom") as page:
            return _bom_list(page)
    with Page(request, "bom") as page:
        return _bom_render(page, request, mode, request.GET.get("parent", ""),
                           request.GET.get("new_sku", ""), request.GET.get("new_name", ""),
                           request.GET.get("new_type", "BULK"), None)


def _bom_list(page: Page):
    """Every parent product (BULK and FG) with its stock and tree size. Each row opens its tree page."""
    L = page.L
    catalog = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams FROM Catalog", page.conn)
    counts = dict(page.conn.execute("SELECT parent_sku, COUNT(*) FROM BOM GROUP BY parent_sku").fetchall())
    parents = catalog[catalog["item_type"].isin(PARENT_TYPES)].sort_values(["item_type", "sku"])
    rows = []
    for r in parents.itertuples():
        is_w = r.item_type == "BULK"
        stock = float((r.weight_grams if is_w else r.qty_units) or 0)
        rows.append({
            "sku": r.sku, "name": r.name or "", "type": r.item_type,
            "stock": page.fmt(stock, is_w),
            "components": int(counts.get(r.sku, 0)),
            "url": reverse("bom_tree", args=[r.sku]),
        })
    return page.render(
        "erp/bom_list.html",
        title=L("עצי מוצר (BOM)", "Product trees (BOM)"),
        subtitle=L("כל מוצרי האב. לחץ על \"פתח\" כדי לראות את המלאי והיחס של כל רכיב לאב.",
                   "All parent products. Click Open to see each component's stock and its ratio to the parent."),
        rows=rows,
    )


def _tree_lines(page: Page, parent_sku: str):
    return page.conn.execute(
        "SELECT b.component_sku, c.name, c.item_type, b.req_qty_units, b.req_weight_grams, c.qty_units, c.weight_grams "
        "FROM BOM b LEFT JOIN Catalog c ON b.component_sku = c.sku WHERE b.parent_sku = ? ORDER BY b.rowid",
        (parent_sku,),
    ).fetchall()


def _tree_rows(page: Page, parent_sku: str, parent_type: str, depth: int, seen: frozenset) -> list[dict]:
    """Components of one parent. A BULK component also carries its own components (its raw materials),
    one level down, so the FG tree can show the bulk and open it."""
    L = page.L
    parent_unit = L("ק\"ג", "kg") if parent_type == "BULK" else L("יח'", "units")
    per = L(" לכל ק\"ג", " per kg") if parent_type == "BULK" else L(" ליחידה", " per unit")
    rows = []
    for comp_sku, comp_name, comp_type, req_u, req_g, stock_u, stock_g in _tree_lines(page, parent_sku):
        is_w = comp_type in ("RAW", "BULK")
        need = float((req_g if is_w else req_u) or 0)
        stock = float((stock_g if is_w else stock_u) or 0)
        covers = stock / need if need > 0 else None
        children = None
        if comp_type == "BULK" and depth < 2 and comp_sku not in seen:
            children = _tree_rows(page, comp_sku, "BULK", depth + 1, seen | {comp_sku})
        rows.append({
            "sku": comp_sku, "name": comp_name or "?", "type": comp_type or "—",
            "stock": page.fmt(stock, is_w),
            "ratio": page.fmt(need, is_w) + per,
            "covers": f"{covers:,.1f} {parent_unit}" if covers is not None else "—",
            "covers_value": covers,
            "children": children,
            "url": reverse("bom_tree", args=[comp_sku]) if comp_type == "BULK" else "",
        })
    return rows


@login_required
def bom_tree(request, sku: str):
    """One parent product: its components, with each bulk opening to its raw materials."""
    with Page(request, "bom") as page:
        L = page.L
        catalog = pd.read_sql("SELECT sku, name, item_type, qty_units, weight_grams FROM Catalog", page.conn).set_index("sku")
        if sku not in catalog.index or catalog.loc[sku, "item_type"] not in PARENT_TYPES:
            raise Http404("not a parent product")
        parent = catalog.loc[sku]
        ptype = parent["item_type"]
        parent_unit = L("ק\"ג", "kg") if ptype == "BULK" else L("יח'", "units")
        rows = _tree_rows(page, sku, ptype, 0, frozenset({sku}))
        values = [r["covers_value"] for r in rows if r["covers_value"] is not None]
        bottleneck = min(values) if values else None
        # Two branches under the product: packaging, and the material (the bulk formula and its raw materials).
        branches = [
            {"label": L("אריזה", "Packaging"), "rows": [r for r in rows if r["type"] == "PKG"]},
            {"label": L("חומר", "Material"), "rows": [r for r in rows if r["type"] != "PKG"]},
        ]
        branches = [b for b in branches if b["rows"]]
        return page.render(
            "erp/bom_tree.html",
            branches=branches,
            parent_name=parent["name"] or "",
            title=f"{sku} · {parent['name'] or ''}",
            subtitle=L("מלאי הרכיבים והיחס שלהם למוצר האב. בלק פתוח מציג את חומרי הגלם שלו.",
                       "Component stock and each component's ratio to the parent. Open a bulk to see its raw materials."),
            parent_sku=sku,
            parent_type=ptype,
            parent_stock=page.fmt(float((parent["weight_grams"] if ptype == "BULK" else parent["qty_units"]) or 0), ptype == "BULK"),
            headers=[L('מק"ט', "SKU"), L("שם רכיב", "Component"), L("סוג", "Type"), L("מלאי נוכחי", "Stock on hand"),
                     L("יחס לאב", "Ratio to parent"), L("מספיק ל", "Enough for")],
            rows=rows,
            components_count=len(rows),
            bottleneck=f"{bottleneck:,.1f} {parent_unit}" if bottleneck is not None else "—",
            edit_url=reverse("bom") + f"?mode=existing&parent={sku}",
        )


def _bom_save(page: Page, request):
    L = page.L
    post = request.POST
    catalog = pd.read_sql("SELECT sku, name, item_type FROM Catalog", page.conn)
    types = catalog.set_index("sku")["item_type"].to_dict()
    names = catalog.set_index("sku")["name"].fillna("").to_dict()
    mode = post.get("mode", "existing")
    if mode == "new":
        parent_sku = post.get("new_sku", "").strip()
        parent_name = post.get("new_name", "").strip()
        parent_type = post.get("new_type", "BULK")
    else:
        parent_sku = post.get("parent", "")
        parent_name = names.get(parent_sku, "")
        parent_type = types.get(parent_sku, "BULK")
    rows = _bom_rows_from_post(post)

    errors = []
    if mode == "new" and parent_sku in types:
        errors.append(L("המק\"ט הזה כבר קיים בקטלוג.", "This SKU already exists in the catalog."))
    if not parent_sku:
        errors.append(L("יש להזין מק\"ט למוצר.", "Enter a SKU for the product."))
    else:
        errors += validate_bom(parent_sku, parent_type, rows, types)
    if mode == "new" and not parent_name:
        errors.append(L("יש להזין שם למוצר החדש.", "Enter a name for the new product."))
    if not errors and not post.get("confirmed"):
        errors.append(L("יש לאשר את העץ לפני השמירה.", "Confirm the tree before saving."))

    if errors:
        for e in errors:
            page.error(e)
        return _bom_render(page, request, mode, parent_sku if mode == "existing" else "",
                           parent_sku if mode == "new" else "", parent_name if mode == "new" else "",
                           parent_type if mode == "new" else "BULK", rows)

    page.push_backup("stock", L(f"עץ מוצר {parent_sku}", f"Product tree {parent_sku}"))
    if mode == "new":
        page.conn.execute(
            "INSERT INTO Catalog (sku, name, item_type, primary_warehouse) VALUES (?,?,?,?)",
            (parent_sku, parent_name, parent_type, "WH_BULK" if parent_type == "BULK" else "WH_FG"),
        )
        if parent_type == "FG":
            page.conn.execute("INSERT OR IGNORE INTO WeeklySchedule (parent_sku) VALUES (?)", (parent_sku,))
    page.conn.execute("DELETE FROM BOM WHERE parent_sku = ?", (parent_sku,))
    page.conn.executemany(
        "INSERT INTO BOM (parent_sku, component_sku, comp_type, req_qty_units, req_weight_grams) VALUES (?,?,?,?,?)",
        to_bom_rows(parent_sku, rows, types, parent_type),
    )
    page.conn.commit()
    page.flash(L(f"עץ המוצר {parent_sku} נשמר ({len(rows)} רכיבים).", f"Saved the tree for {parent_sku} ({len(rows)} components)."))
    return redirect(f"/bom/?mode=existing&parent={parent_sku}")


def _bom_render(page: Page, request, mode: str, parent_sku: str, new_sku: str, new_name: str, new_type: str, posted_rows):
    L = page.L
    catalog = pd.read_sql("SELECT sku, name, item_type FROM Catalog", page.conn)
    types = catalog.set_index("sku")["item_type"].to_dict()
    names = catalog.set_index("sku")["name"].fillna("").to_dict()
    parents = catalog[catalog["item_type"].isin(PARENT_TYPES)].sort_values("sku")

    if mode == "new":
        parent_sku = new_sku.strip()
        parent_name = new_name.strip()
        parent_type = new_type if new_type in PARENT_TYPES else "BULK"
        current = []
    else:
        if parent_sku not in set(parents["sku"]) and not parents.empty:
            parent_sku = parents["sku"].iloc[0]
        parent_name = names.get(parent_sku, "")
        parent_type = types.get(parent_sku, "BULK")
        if posted_rows is not None:
            current = posted_rows
        else:
            current = [
                {"component_sku": comp, "quantity": float(grams if comp_type in ("RAW", "BULK") else qty_u)}
                for comp, comp_type, qty_u, grams in page.conn.execute(
                    "SELECT component_sku, comp_type, req_qty_units, req_weight_grams FROM BOM WHERE parent_sku = ? ORDER BY rowid",
                    (parent_sku,),
                ).fetchall()
            ] if parent_sku else []

    allowed = allowed_component_types(parent_type)
    options = [{"sku": r.sku, "label": f"{r.sku} - {r.name}"} for r in catalog[catalog["item_type"].isin(allowed)].itertuples()]
    rows = current + [{"component_sku": "", "quantity": None} for _ in range(BOM_NEW_ROWS)]
    for r in rows:
        r["comp_type"] = types.get(r.get("component_sku") or "", "")
    filled_count = sum(1 for r in rows if r.get("component_sku"))
    raw_count = sum(1 for r in rows if r.get("comp_type") == "RAW")
    bulk_count = sum(1 for r in rows if r.get("comp_type") == "BULK")
    pkg_count = sum(1 for r in rows if r.get("comp_type") == "PKG")
    return page.render(
        "erp/bom.html",
        title=L("עצי מוצר (BOM)", "Product trees (BOM)"),
        subtitle=L(
            "הוספה ועריכה של עצי מוצר. בלק (BULK) מורכב מחומרי גלם (RAW) לכל ק\"ג. מוצר סופי (FG) מורכב מבלקים (BULK) ומאריזות (PKG) ליחידה.",
            "Add or edit product trees. A bulk (BULK) is made from raw materials (RAW) per kg. A finished product (FG) is made from bulks (BULK) and packaging (PKG) per unit.",
        ),
        mode=mode,
        parents=[{"sku": r.sku, "label": f"{r.sku} - {r.name}"} for r in parents.itertuples()],
        has_parents=not parents.empty,
        parent_sku=parent_sku,
        parent_name=parent_name,
        parent_type=parent_type,
        rows=rows,
        filled_count=filled_count,
        raw_count=raw_count,
        bulk_count=bulk_count,
        pkg_count=pkg_count,
        parent_count=len(parents),
        row_count=len(rows),
        options=options,
        new_sku=new_sku,
        new_name=new_name,
        new_type=new_type,
        product_types=PARENT_TYPES,
    )
