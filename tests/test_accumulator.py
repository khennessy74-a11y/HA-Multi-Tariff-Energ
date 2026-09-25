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



def test_accounting_state_storage_round_trip():
    """Persist and restore exact Decimal totals and meter baselines."""
    from datetime import date
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import (
        AccountingState,
        accounting_state_from_storage,
    )

    state = AccountingState.create(date(2026, 9, 25))
    state.today.add_import("Day", Decimal("1.234"), Decimal("0.3017"))
    state.month_totals.add_import("Day", Decimal("9.876"), Decimal("0.3017"))
    state.today.add_export(Decimal("0.456"), Decimal("0.15"))
    state.import_meter.last_value = Decimal("12345.6789")
    state.export_meter.last_value = Decimal("456.789")
    state.solar_meter.last_value = Decimal("987.654")
    state.standing_charge_applied_day = "2026-09-25"

    restored = accounting_state_from_storage(state.as_storage_dict())

    assert restored.day == state.day
    assert restored.month == state.month
    assert restored.today == state.today
    assert restored.month_totals == state.month_totals
    assert restored.import_meter.last_value == Decimal("12345.6789")
    assert restored.export_meter.last_value == Decimal("456.789")
    assert restored.solar_meter.last_value == Decimal("987.654")
    assert restored.standing_charge_applied_day == "2026-09-25"
