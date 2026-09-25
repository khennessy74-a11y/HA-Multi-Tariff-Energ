"""Tests for cumulative meter and accounting state."""

from datetime import date
from decimal import Decimal

from custom_components.multi_tariff_energy.accumulator import (
    AccountingState,
    MeterTracker,
    PeriodTotals,
)


def test_meter_tracker_uses_baseline_and_handles_reset() -> None:
    meter = MeterTracker()
    assert meter.update(Decimal("100")) == 0
    assert meter.update(Decimal("101.25")) == Decimal("1.25")
    assert meter.update(Decimal("3")) == 0
    assert meter.update(Decimal("4.5")) == Decimal("1.5")


def test_period_totals_import_export_and_net() -> None:
    totals = PeriodTotals()
    totals.add_import("Day", Decimal("2"), Decimal("0.30"))
    totals.add_export(Decimal("1"), Decimal("0.20"))
    assert totals.import_kwh == Decimal("2")
    assert totals.import_cost == Decimal("0.60")
    assert totals.export_credit == Decimal("0.20")
    assert totals.net_cost == Decimal("0.40")


def test_standing_charge_is_idempotent() -> None:
    state = AccountingState.create(date(2026, 9, 25))
    state.apply_standing_charge(
        date(2026, 9, 25), Decimal("0.60"), Decimal("10")
    )
    state.apply_standing_charge(
        date(2026, 9, 25), Decimal("0.60"), Decimal("10")
    )
    assert state.today.standing_charge == Decimal("0.60")
    assert state.today.vat == Decimal("0.06")
    assert state.month_totals.standing_charge == Decimal("0.60")


def test_rollover_resets_day_and_month() -> None:
    state = AccountingState.create(date(2026, 9, 30))
    state.today.import_kwh = Decimal("2")
    state.month_totals.import_kwh = Decimal("20")
    state.rollover(date(2026, 10, 1))
    assert state.today.import_kwh == 0
    assert state.month_totals.import_kwh == 0
    assert state.day == "2026-10-01"
    assert state.month == "2026-10"
