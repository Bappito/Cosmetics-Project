from datetime import date

import cosmetics_erp.services.planning as planning
from cosmetics_erp.services.planning import PlanningService, current_plan_start


def test_plan_start_is_sunday_on_or_before_today(monkeypatch):
    monkeypatch.setattr(planning, "PLAN_START_OVERRIDE", None)
    start = current_plan_start(date(2026, 11, 25))  # a Wednesday
    assert start == date(2026, 11, 22)
    assert start.weekday() == 6


def test_override_pins_plan_start(monkeypatch):
    monkeypatch.setattr(planning, "PLAN_START_OVERRIDE", date(2026, 1, 4))
    assert current_plan_start(date(2026, 11, 25)) == date(2026, 1, 4)


def test_eta_weeks_relative_to_plan_start():
    service = PlanningService(periods=[], translate=lambda he, en: en, plan_start=date(2026, 11, 22))
    assert service.eta_to_week("2026-11-01") == "W1"
    assert service.eta_to_week("2026-11-30") == "W2"
    assert service.eta_to_week("2027-03-01") is None


def test_plan_start_is_stored_and_does_not_move(conn):
    from cosmetics_erp.services.planning import get_plan_start, set_plan_start
    set_plan_start(conn, date(2026, 11, 22))
    assert get_plan_start(conn) == date(2026, 11, 22)
    set_plan_start(conn, date(2026, 12, 6))
    assert get_plan_start(conn) == date(2026, 12, 6)


def test_week_labels_show_real_dates():
    from cosmetics_erp.config.i18n import build_plan_periods
    periods = build_plan_periods(False, date(2026, 11, 22))
    assert periods[0][0] == "W1"
    assert periods[0][2] == "Week 1"
    assert periods[1][2] == "Week 2"
    assert periods[0][1] == "Nov 2026"
    hebrew = build_plan_periods(True, date(2026, 11, 22))
    assert hebrew[0][2] == "שבוע 1"
    assert hebrew[0][1] == "נובמבר 2026"
