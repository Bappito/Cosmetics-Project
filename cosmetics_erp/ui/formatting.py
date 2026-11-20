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
