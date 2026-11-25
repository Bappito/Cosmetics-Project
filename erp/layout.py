"""Admin-changeable layout: the order of the sidebar menu. Stored in the Django database."""
from __future__ import annotations

from erp.models import LayoutSetting

MENU_KEY = "menu_order"


def saved_menu_order() -> list[str]:
    row = LayoutSetting.objects.filter(key=MENU_KEY).first()
    return list(row.value) if row and isinstance(row.value, list) else []


def save_menu_order(keys: list[str]) -> None:
    LayoutSetting.objects.update_or_create(key=MENU_KEY, defaults={"value": list(keys)})


def sort_by_saved_order(items: list[dict], order: list[str]) -> list[dict]:
    """Items in the saved order first; any item not in the saved order keeps its default place after them."""
    position = {key: i for i, key in enumerate(order)}
    fallback = len(position)
    indexed = list(enumerate(items))
    indexed.sort(key=lambda pair: (position.get(pair[1]["key"], fallback), pair[0]))
    return [item for _, item in indexed]
