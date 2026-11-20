from __future__ import annotations

from datetime import date, datetime
from typing import Callable, Sequence


PLAN_START = date(2026, 11, 15)


class PlanningService:
    def __init__(
        self,
        periods: Sequence[tuple[str, str, str]],
        translate: Callable[[str, str], str],
        plan_start: date = PLAN_START,
    ) -> None:
        self.periods = periods
        self.translate = translate
        self.plan_start = plan_start

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
