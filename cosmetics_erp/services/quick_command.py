"""Rule-based parser for the quick stock command, e.g. "add 5 kg to 1001" or "תוסיף 300 יחידות ל-3001".

No external AI service is called. The amount is the first number, the SKU is the last one, and the
unit is read from keywords in the text.
"""

from __future__ import annotations

import re

WEIGHT_TYPES = ("RAW", "BULK")


class CommandError(ValueError):
    """Raised with a message key that the view turns into a translated message."""

    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def parse_command(text: str) -> dict:
    """Return {"sku", "amount", "unit"} where unit is "kg", "g" or "units".

    Raises CommandError with one of: need_two_numbers, not_positive, unit_whole_numbers.
    The caller checks the SKU and its item type, because only the catalog knows them.
    """
    nums = re.findall(r"(-?\d+(?:[.,]\d+)?)", text)
    if len(nums) < 2:
        raise CommandError("need_two_numbers")
    amount = float(nums[0].replace(",", "."))
    # "ל-1001" is "to 1001": the regex reads the hyphen as a minus sign, so strip it from the SKU.
    sku = nums[-1].lstrip("-")
    if amount <= 0:
        raise CommandError("not_positive")

    normalized = text.casefold()
    if "קילו" in normalized or 'ק"ג' in normalized or "kg" in normalized:
        unit = "kg"
    elif "גרם" in normalized or "gram" in normalized or re.search(r"\bg\b", normalized):
        unit = "g"
    elif "יחיד" in normalized or "יח'" in normalized or "unit" in normalized:
        unit = "units"
    else:
        unit = None
    return {"sku": sku, "amount": amount, "unit": unit}


def added_base_amount(amount: float, unit: str) -> float:
    """Convert the typed amount to base units (grams for weight items, units otherwise)."""
    return amount * 1000.0 if unit == "kg" else amount


def check_unit_for_type(item_type: str, unit: str | None, amount: float) -> None:
    """Raise CommandError when the unit does not fit the item type."""
    if item_type in WEIGHT_TYPES:
        if unit not in ("kg", "g"):
            raise CommandError("weight_needs_unit")
    elif unit != "units":
        raise CommandError("units_needed")
    if unit == "units" and not float(amount).is_integer():
        raise CommandError("unit_whole_numbers")
