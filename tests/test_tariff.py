"""Tests for tariff calculation helpers."""

from datetime import datetime, time
from decimal import Decimal

from custom_components.multi_tariff_energy.tariff import (
    TariffPeriod,
    active_tariff,
    energy_cost,
    gross_cost,
    net_cost,
)


def test_tariff_period_crosses_midnight() -> None:
    period = TariffPeriod(
        name="Night",
        start=time(23, 0),
        end=time(8, 0),
        rate=Decimal("0.15"),
    )
    assert period.active_at(datetime(2026, 9, 25, 1, 0))
    assert period.active_at(datetime(2026, 9, 25, 23, 30))
    assert not period.active_at(datetime(2026, 9, 25, 12, 0))


def test_active_tariff() -> None:
    periods = [
        TariffPeriod("Night", time(0), time(8), Decimal("0.15")),
        TariffPeriod("Day", time(8), time(17), Decimal("0.32")),
        TariffPeriod("Peak", time(17), time(19), Decimal("0.42")),
        TariffPeriod("Day", time(19), time(23), Decimal("0.32")),
        TariffPeriod("Night", time(23), time(0), Decimal("0.15")),
    ]
    assert active_tariff(periods, datetime(2026, 9, 25, 18, 0)).name == "Peak"
    assert active_tariff(periods, datetime(2026, 9, 25, 23, 30)).name == "Night"


def test_bill_calculation() -> None:
    imported = energy_cost(Decimal("10"), Decimal("0.30"))
    gross = gross_cost(imported, Decimal("0.60"), Decimal("10"))
    exported = energy_cost(Decimal("2"), Decimal("0.20"))
    assert gross == Decimal("3.960")
    assert net_cost(gross, exported) == Decimal("3.560")



def test_multiple_windows_same_tariff() -> None:
    from custom_components.multi_tariff_energy.tariff import tariffs_from_config

    periods = tariffs_from_config(
        {
            "tariff_windows": [
                {"name": "Day", "start": "08:00", "end": "17:00", "rate": "0.30"},
                {"name": "Peak", "start": "17:00", "end": "19:00", "rate": "0.42"},
                {"name": "Day", "start": "19:00", "end": "23:00", "rate": "0.30"},
                {"name": "Night", "start": "23:00", "end": "08:00", "rate": "0.15"},
            ]
        }
    )
    assert len(periods) == 4
    assert active_tariff(periods, datetime(2026, 9, 25, 9, 0)).name == "Day"
    assert active_tariff(periods, datetime(2026, 9, 25, 18, 0)).name == "Peak"
    assert active_tariff(periods, datetime(2026, 9, 25, 20, 0)).name == "Day"
    assert active_tariff(periods, datetime(2026, 9, 25, 1, 0)).name == "Night"
