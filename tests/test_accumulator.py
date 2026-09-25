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



def test_import_vat_exclusive():
    """Add VAT on top when tariff rates exclude VAT."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import PeriodTotals

    totals = PeriodTotals()
    totals.add_import(
        "Day", Decimal("10"), Decimal("0.30"), Decimal("20"), False, True
    )
    assert totals.import_cost == Decimal("3.00")
    assert totals.vat == Decimal("0.60")
    assert totals.net_cost == Decimal("3.60")


def test_import_vat_inclusive_is_not_double_counted():
    """Extract VAT component without adding it again to an inclusive rate."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import PeriodTotals

    totals = PeriodTotals()
    totals.add_import(
        "Day", Decimal("10"), Decimal("0.36"), Decimal("20"), True, True
    )
    assert totals.import_cost == Decimal("3.60")
    assert totals.vat == Decimal("0.60")
    assert totals.net_cost == Decimal("3.60")


def test_import_vat_can_be_disabled():
    """Do not account VAT when import VAT is disabled."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import PeriodTotals

    totals = PeriodTotals()
    totals.add_import(
        "Day", Decimal("10"), Decimal("0.30"), Decimal("20"), False, False
    )
    assert totals.import_cost == Decimal("3.00")
    assert totals.vat == Decimal("0")
    assert totals.net_cost == Decimal("3.00")



def test_rollover_preserves_previous_periods():
    """Move completed daily and monthly totals into previous-period snapshots."""
    from datetime import date
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import AccountingState

    state = AccountingState.create(date(2026, 9, 30))
    state.today.add_import("Day", Decimal("2"), Decimal("0.30"))
    state.month_totals.add_import("Day", Decimal("20"), Decimal("0.30"))

    state.rollover(date(2026, 10, 1))

    assert state.yesterday.import_kwh == Decimal("2")
    assert state.yesterday.import_cost == Decimal("0.60")
    assert state.last_month.import_kwh == Decimal("20")
    assert state.last_month.import_cost == Decimal("6.00")
    assert state.today.import_kwh == Decimal("0")
    assert state.month_totals.import_kwh == Decimal("0")



def test_billing_cycle_rollover():
    """Roll billing totals on the configured billing day."""
    from datetime import date
    from decimal import Decimal

    from custom_components.multi_tariff_energy.accumulator import AccountingState

    state = AccountingState.create(date(2026, 9, 14))
    state.rollover_billing_cycle(date(2026, 9, 14), 15)
    assert state.billing_cycle_start == "2026-08-15"

    state.billing_cycle.add_import("Day", Decimal("12"), Decimal("0.30"))
    state.rollover_billing_cycle(date(2026, 9, 15), 15)

    assert state.billing_cycle_start == "2026-09-15"
    assert state.previous_billing_cycle.import_kwh == Decimal("12")
    assert state.previous_billing_cycle.import_cost == Decimal("3.60")
    assert state.billing_cycle.import_kwh == Decimal("0")


def test_billing_cycle_rollover_across_new_year():
    """Calculate the previous cycle correctly across January."""
    from datetime import date

    from custom_components.multi_tariff_energy.accumulator import AccountingState

    state = AccountingState.create(date(2027, 1, 10))
    state.rollover_billing_cycle(date(2027, 1, 10), 15)

    assert state.billing_cycle_start == "2026-12-15"


def test_standing_charge_is_included_once_in_billing_cycle():
    """Include daily standing charge and VAT in the active billing cycle."""
    state = AccountingState.create(date(2026, 9, 25))
    state.rollover_billing_cycle(date(2026, 9, 25), 15)

    state.apply_standing_charge(
        date(2026, 9, 25), Decimal("0.60"), Decimal("10")
    )
    state.apply_standing_charge(
        date(2026, 9, 25), Decimal("0.60"), Decimal("10")
    )

    assert state.billing_cycle.standing_charge == Decimal("0.60")
    assert state.billing_cycle.vat == Decimal("0.06")
    assert state.billing_cycle.vat_added == Decimal("0.06")
    assert state.billing_cycle.net_cost == Decimal("0.66")
