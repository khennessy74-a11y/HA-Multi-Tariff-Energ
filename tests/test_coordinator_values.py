"""Test the coordinator value map without requiring a running HA instance."""

from datetime import date
from decimal import Decimal

from custom_components.multi_tariff_energy.accumulator import AccountingState


def test_expected_daily_and_monthly_totals() -> None:
    state = AccountingState.create(date(2026, 9, 25))
    state.today.add_import("Day", Decimal("3"), Decimal("0.30"))
    state.month_totals.add_import("Day", Decimal("30"), Decimal("0.30"))
    state.today.add_export(Decimal("1"), Decimal("0.20"))
    state.month_totals.add_export(Decimal("10"), Decimal("0.20"))

    assert state.today.import_cost == Decimal("0.90")
    assert state.today.export_credit == Decimal("0.20")
    assert state.today.net_cost == Decimal("0.70")
    assert state.month_totals.import_cost == Decimal("9.00")
    assert state.month_totals.export_credit == Decimal("2.00")
    assert state.month_totals.net_cost == Decimal("7.00")
