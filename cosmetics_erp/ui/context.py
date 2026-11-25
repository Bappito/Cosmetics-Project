from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class PageContext:
    CLOSED_PO_STATUSES: tuple[str, str]
    L: Callable[[str, str], str]
    PLAN_PERIODS: list[tuple[str, str, str]]
    UI: Mapping[str, str]
    add_batch: Callable[..., Any]
    apply_picks: Callable[..., Any]
    batch_exists: Callable[..., Any]
    inventory_service: Any
    conn: sqlite3.Connection
    eta_to_week: Callable[..., Any]
    eta_week_label: Callable[..., Any]
    fmt_val: Callable[..., Any]
    gen_batch_no: Callable[..., Any]
    get_incoming_map: Callable[..., Any]
    get_sku_expiry_summary: Callable[..., Any]
    is_he: bool
    log_consumption: Callable[..., Any]
    log_move: Callable[..., Any]
    parse_date: Callable[..., Any]
    plan_fefo: Callable[..., Any]
    push_backup: Callable[..., Any]
    reconcile_batches: Callable[..., Any]
    render_quick_planner: Callable[..., Any]
    render_undo_button: Callable[..., Any]
    render_where_used_simulator: Callable[..., Any]
    trace_chain: Callable[..., Any]
    u_label: str
    w_factor: float
    w_label: str
