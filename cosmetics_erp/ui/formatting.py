from datetime import datetime


def format_date(value: object, *, is_he: bool) -> str:
    if value is None:
        return "—"
    text = str(value).strip()
    if not text or text.lower() in {"nan", "nat", "<na>"}:
        return "—"
    try:
        parsed = datetime.strptime(text[:10], "%Y-%m-%d")
    except ValueError:
        return text
    return parsed.strftime("%d/%m/%Y") if is_he else parsed.strftime("%b %d, %Y")


def format_value(
    val_in_base: float,
    is_weight_based: bool,
    *,
    use_kg: bool,
    w_factor: float,
    w_label: str,
    u_label: str,
) -> str:
    is_neg = val_in_base < -1e-6
    abs_val = abs(val_in_base)
    if is_weight_based:
        scaled = abs_val / w_factor
        num_str = f"{scaled:,.2f}".rstrip("0").rstrip(".") if use_kg else f"{scaled:,.0f}"
        unit = w_label
    else:
        num_str = f"{abs_val:,.0f}"
        unit = u_label
    if is_neg:
        return f"<span dir='ltr'>-{num_str}</span> {unit}"
    return f"{num_str} {unit}"


SKU_KEYS = ("sku", "SKU", "מק\"ט", 'מק"ט')
NAME_KEYS = ("name", "Item", "פריט", "Item Name")


def sku_first(columns, is_he: bool) -> list:
    """Column order for dataframes and editors: SKU first, item name second.

    Dataframe grids draw the first column on the left, so in Hebrew the order is
    reversed to put SKU on the right and the name just to its left.
    """
    cols = list(columns)
    sku = next((c for c in cols if c in SKU_KEYS), None)
    name = next((c for c in cols if c in NAME_KEYS), None)
    head = [c for c in (sku, name) if c is not None]
    order = head + [c for c in cols if c not in head]
    return list(reversed(order)) if is_he else order
