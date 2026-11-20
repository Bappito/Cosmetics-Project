from __future__ import annotations

from numbers import Real
from typing import Sequence

import pandas as pd


def _normalize(value: object) -> object:
    if pd.isna(value):
        return None
    if isinstance(value, Real) and not isinstance(value, bool):
        return round(float(value), 10)
    return str(value).strip()


def summarize_editor_changes(
    before: pd.DataFrame,
    after: pd.DataFrame,
    key_column: str,
    compare_columns: Sequence[str] | None = None,
) -> tuple[list[str], list[str], list[str]]:
    columns = list(compare_columns or (column for column in after.columns if column != key_column))

    def rows_by_key(frame: pd.DataFrame) -> dict[str, tuple[object, ...]]:
        rows: dict[str, tuple[object, ...]] = {}
        for _, row in frame.iterrows():
            key = _normalize(row[key_column])
            if key:
                rows[str(key)] = tuple(_normalize(row[column]) for column in columns)
        return rows

    previous = rows_by_key(before)
    current = rows_by_key(after)
    previous_keys = set(previous)
    current_keys = set(current)
    added = sorted(current_keys - previous_keys)
    removed = sorted(previous_keys - current_keys)
    changed = sorted(
        key for key in previous_keys & current_keys if previous[key] != current[key]
    )
    return added, removed, changed
