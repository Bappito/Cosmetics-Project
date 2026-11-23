from __future__ import annotations

"""Rules for product trees (BOM) edited from the app.

A parent's components must follow the production flow:
    BULK (made per kg)  <- RAW components, quantity in grams per kg
    FG   (packed per unit) <- BULK components (grams per unit) or PKG components (units per unit)
"""

ALLOWED_COMPONENTS = {
    "BULK": {"RAW": "weight"},
    "FG": {"BULK": "weight", "PKG": "qty"},
}
PARENT_TYPES = tuple(ALLOWED_COMPONENTS.keys())


def allowed_component_types(parent_type: str) -> list[str]:
    return list(ALLOWED_COMPONENTS.get(parent_type, {}).keys())


def validate_bom(parent_sku: str, parent_type: str, rows: list[dict], catalog_types: dict[str, str]) -> list[str]:
    """Return a list of problems. An empty list means the tree can be saved.

    rows: dicts with component_sku and quantity (grams for weight components, units for PKG).
    catalog_types: sku -> item_type for every catalog item.
    """
    errors: list[str] = []
    if parent_type not in ALLOWED_COMPONENTS:
        return [f"סוג מוצר האב חייב להיות BULK או FG / Parent type must be BULK or FG (got {parent_type})."]
    if not rows:
        errors.append("לעץ המוצר חייב להיות לפחות רכיב אחד. / The tree needs at least one component.")
    seen = set()
    rules = ALLOWED_COMPONENTS[parent_type]
    for index, row in enumerate(rows, start=1):
        comp = str(row.get("component_sku") or "").strip()
        qty = row.get("quantity")
        if not comp:
            errors.append(f"שורה {index}: חסר מק\"ט רכיב. / Row {index}: missing component SKU.")
            continue
        if comp == parent_sku:
            errors.append(f"שורה {index}: מוצר לא יכול להכיל את עצמו. / Row {index}: a product cannot contain itself.")
        if comp in seen:
            errors.append(f"שורה {index}: הרכיב {comp} מופיע פעמיים. / Row {index}: {comp} appears twice.")
        seen.add(comp)
        comp_type = catalog_types.get(comp)
        if comp_type is None:
            errors.append(f"שורה {index}: המק\"ט {comp} לא קיים בקטלוג. / Row {index}: {comp} is not in the catalog.")
            continue
        if comp_type not in rules:
            errors.append(
                f"שורה {index}: {parent_type} לא יכול לכלול רכיב מסוג {comp_type}. / Row {index}: a {parent_type} cannot contain a {comp_type} component."
            )
        try:
            value = float(qty)
        except (TypeError, ValueError):
            value = None
        if value is None or value <= 0:
            errors.append(f"שורה {index}: הכמות חייבת להיות מספר גדול מאפס. / Row {index}: quantity must be greater than zero.")
    return errors


def to_bom_rows(parent_sku: str, rows: list[dict], catalog_types: dict[str, str], parent_type: str) -> list[tuple]:
    """Convert editor rows into BOM table tuples (parent, component, comp_type, req_qty_units, req_weight_grams)."""
    rules = ALLOWED_COMPONENTS[parent_type]
    out = []
    for row in rows:
        comp = str(row["component_sku"]).strip()
        comp_type = catalog_types[comp]
        qty = float(row["quantity"])
        if rules[comp_type] == "weight":
            out.append((parent_sku, comp, comp_type, 0.0, qty))
        else:
            out.append((parent_sku, comp, comp_type, qty, 0.0))
    return out
