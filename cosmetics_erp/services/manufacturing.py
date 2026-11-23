from __future__ import annotations

"""Production (bulk) and packaging runs: plan the components with FEFO, then post the movements.

The UI collects the inputs and shows messages. Everything that changes stock lives here,
so it can be tested without Streamlit.
"""

from datetime import date


def plan_components(svc, components: list[dict]) -> tuple[list[dict], list[dict]]:
    """components: dicts with sku, need (base units), is_weight and from_wh.

    Returns (plans, shortages). A plan holds the FEFO picks for a component. A shortage
    lists how much valid (not expired) stock is missing for it.
    """
    plans, shortages = [], []
    for comp in components:
        picks, short = svc.plan_fefo(comp["sku"], comp["need"], comp["is_weight"])
        plan = dict(comp, picks=picks)
        plans.append(plan)
        if short > 1e-6:
            shortages.append({"sku": comp["sku"], "short": short, "is_weight": comp["is_weight"]})
    return plans, shortages


def expiry_cap(plans: list[dict], requested: date | str) -> tuple[str, bool, str | None]:
    """Output expiry is capped at the earliest expiry of the components it uses.

    Returns (expiry as YYYY-MM-DD, was_capped, limiting expiry or None).
    """
    requested_s = requested if isinstance(requested, str) else requested.strftime("%Y-%m-%d")
    limiting = None
    for plan in plans:
        for pick in plan["picks"]:
            exp = pick["expiry"]
            if exp and (limiting is None or exp < limiting):
                limiting = exp
    if limiting and requested_s > limiting:
        return limiting, True, limiting
    return requested_s, False, limiting


def _catalog_column(is_weight: bool) -> str:
    return "weight_grams" if is_weight else "qty_units"


def post_run(conn, svc, *, kind: str, parent_sku: str, batch_no: str, plans: list[dict], expiry: str,
             output_amount: float, output_is_weight: bool, now_d: str, kg_display: float | None = None) -> dict:
    """Post a production or packaging run. kind is "production" or "packaging".

    Consumes the planned picks, logs consumption and movements, adds the output batch,
    and updates catalog balances. Does not commit until the end.
    """
    if kind not in ("production", "packaging"):
        raise ValueError(f"unknown run kind: {kind}")
    exp_s, capped, limiting = expiry_cap(plans, expiry)
    ref = f"PROD {parent_sku}" if kind == "production" else f"PACK {parent_sku}"
    ref_batch = f"{ref} / {batch_no}"

    for plan in plans:
        sku, need, is_weight, picks = plan["sku"], plan["need"], plan["is_weight"], plan["picks"]
        svc.apply_picks(picks, is_weight)
        svc.log_consumption(parent_sku, batch_no, sku, picks, is_weight, ref)
        svc.log_move(sku, plan["from_wh"], "WH_LINE", need, is_weight, ref_batch)
        col = _catalog_column(is_weight)
        if kind == "production":
            note = f"-{need / 1000:.2f} ק\"ג לבלק {parent_sku}"
            conn.execute(f"UPDATE Catalog SET {col} = MAX(0, {col} - ?), stock_movements = ? WHERE sku = ?", (need, note, sku))
        elif is_weight:
            note = f"-{need / 1000:.2f} ק\"ג לאריזת {parent_sku}"
            conn.execute(f"UPDATE Catalog SET {col} = MAX(0, {col} - ?), stock_movements = ? WHERE sku = ?", (need, note, sku))
        else:
            note = f"-{need:.0f} יח' לאריזה {parent_sku}"
            conn.execute(f"UPDATE Catalog SET {col} = MAX(0, {col} - ?), stock_movements = ? WHERE sku = ?", (need, note, sku))

    source = "PRODUCTION" if kind == "production" else "PACKING"
    svc.add_batch(parent_sku, batch_no, output_amount, output_is_weight, exp_s, source)
    to_wh = "WH_BULK" if kind == "production" else "WH_FG"
    svc.log_move(parent_sku, "WH_LINE", to_wh, output_amount, output_is_weight, ref_batch)
    col = _catalog_column(output_is_weight)
    if kind == "production":
        kg = kg_display if kg_display is not None else output_amount / 1000.0
        conn.execute(
            f"UPDATE Catalog SET {col} = {col} + ?, stock_movements = ?, last_stock_entry = ? WHERE sku = ?",
            (output_amount, f"+{kg:.1f} ק\"ג מקו ייצור", f"{now_d} (+{kg:.1f} ק\"ג)", parent_sku),
        )
    else:
        conn.execute(
            f"UPDATE Catalog SET {col} = {col} + ?, last_stock_entry = ? WHERE sku = ?",
            (output_amount, f"{now_d} (+{output_amount:.0f} יח')", parent_sku),
        )
    conn.commit()
    return {"expiry": exp_s, "capped": capped, "limiting": limiting}
