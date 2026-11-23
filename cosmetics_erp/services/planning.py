from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Sequence

from ..config.constants import PLAN_START_OVERRIDE

PLAN_START_KEY = "plan_start"


def get_plan_start(conn) -> date:
    """The stored start of the eight-week plan. The plan does not move on its own."""
    row = conn.execute("SELECT value FROM Settings WHERE key = ?", (PLAN_START_KEY,)).fetchone()
    if row:
        return date.fromisoformat(row[0])
    return current_plan_start()


def set_plan_start(conn, value: date) -> None:
    conn.execute(
        "INSERT INTO Settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (PLAN_START_KEY, value.isoformat()),
    )
    conn.commit()


def current_plan_start(today: date | None = None) -> date:
    """Return the Sunday that starts the current week, unless PLAN_START_OVERRIDE is set."""
    if PLAN_START_OVERRIDE:
        return PLAN_START_OVERRIDE
    today = today or date.today()
    return today - timedelta(days=(today.weekday() + 1) % 7)


class PlanningService:
    def __init__(
        self,
        periods: Sequence[tuple[str, str, str]],
        translate: Callable[[str, str], str],
        plan_start: date | None = None,
    ) -> None:
        self.periods = periods
        self.translate = translate
        self.plan_start = plan_start or current_plan_start()

    @staticmethod
    def parse_date(value: object) -> date | None:
        try:
            return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    def eta_to_week(self, eta_str: object) -> str | None:
        eta_date = self.parse_date(eta_str)
        if eta_date is None:
            return None
        delta = (eta_date - self.plan_start).days
        if delta < 0:
            return "W1"
        index = delta // 7
        return f"W{index + 1}" if index < 8 else None

    def eta_week_label(self, eta_str: object) -> str:
        eta_date = self.parse_date(eta_str)
        if eta_date is None:
            return self.translate("אין ETA תקין", "No valid ETA")
        week = self.eta_to_week(eta_str)
        if week is None:
            return self.translate("מחוץ לטווח 8 השבועות", "Beyond W8")
        suffix = self.translate(" (באיחור - נספר ב-W1)", " (overdue - counted in W1)") if eta_date < self.plan_start else ""
        label = next(period[2] for period in self.periods if period[0] == week)
        return f"{week} | {label}{suffix}"
