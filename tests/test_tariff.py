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



def test_next_tariff_change_with_repeated_named_window():
    """Find the next boundary even when a tariff name has multiple windows."""
    from datetime import datetime
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        next_tariff_change,
        parse_time,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("17:00"), Decimal("0.30")),
        TariffPeriod("Peak", parse_time("17:00"), parse_time("19:00"), Decimal("0.42")),
        TariffPeriod("Day", parse_time("19:00"), parse_time("23:00"), Decimal("0.30")),
        TariffPeriod("Night", parse_time("23:00"), parse_time("08:00"), Decimal("0.15")),
    ]

    change = next_tariff_change(periods, datetime(2026, 9, 25, 16, 30))
    assert change is not None
    when, tariff = change
    assert when == datetime(2026, 9, 25, 17, 0)
    assert tariff.name == "Peak"
    assert tariff.rate == Decimal("0.42")


def test_next_tariff_change_crosses_midnight():
    """Find the next boundary across a local midnight."""
    from datetime import datetime
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        next_tariff_change,
        parse_time,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("23:00"), Decimal("0.30")),
        TariffPeriod("Night", parse_time("23:00"), parse_time("08:00"), Decimal("0.15")),
    ]

    change = next_tariff_change(periods, datetime(2026, 9, 25, 23, 30))
    assert change is not None
    when, tariff = change
    assert when == datetime(2026, 9, 26, 8, 0)
    assert tariff.name == "Day"



def test_validate_complete_tariff_schedule():
    """Accept a complete schedule with a repeated tariff name."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        parse_time,
        validate_tariff_periods,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("17:00"), Decimal("0.30")),
        TariffPeriod("Peak", parse_time("17:00"), parse_time("19:00"), Decimal("0.42")),
        TariffPeriod("Day", parse_time("19:00"), parse_time("23:00"), Decimal("0.30")),
        TariffPeriod("Night", parse_time("23:00"), parse_time("08:00"), Decimal("0.15")),
    ]
    assert validate_tariff_periods(periods) == []


def test_validate_tariff_schedule_gap():
    """Reject a schedule with uncovered time."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        parse_time,
        validate_tariff_periods,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("17:00"), Decimal("0.30")),
        TariffPeriod("Night", parse_time("23:00"), parse_time("08:00"), Decimal("0.15")),
    ]
    assert "gap" in validate_tariff_periods(periods)


def test_validate_tariff_schedule_overlap():
    """Reject overlapping tariff windows."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        parse_time,
        validate_tariff_periods,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("20:00"), Decimal("0.30")),
        TariffPeriod("Night", parse_time("19:00"), parse_time("08:00"), Decimal("0.15")),
    ]
    assert "overlap" in validate_tariff_periods(periods)


def test_validate_zero_length_tariff():
    """Reject a tariff whose start and end are identical."""
    from decimal import Decimal

    from custom_components.multi_tariff_energy.tariff import (
        TariffPeriod,
        parse_time,
        validate_tariff_periods,
    )

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("08:00"), Decimal("0.30")),
    ]
    errors = validate_tariff_periods(periods)
    assert "zero_length" in errors
    assert "gap" in errors


def test_next_tariff_change_skips_adjacent_identical_tariff():
    """Do not report a boundary when tariff name and rate do not change."""
    from custom_components.multi_tariff_energy.tariff import next_tariff_change, parse_time

    periods = [
        TariffPeriod("Day", parse_time("08:00"), parse_time("12:00"), Decimal("0.30")),
        TariffPeriod("Day", parse_time("12:00"), parse_time("17:00"), Decimal("0.30")),
        TariffPeriod("Peak", parse_time("17:00"), parse_time("19:00"), Decimal("0.42")),
        TariffPeriod("Night", parse_time("19:00"), parse_time("08:00"), Decimal("0.15")),
    ]
    change = next_tariff_change(periods, datetime(2026, 9, 25, 11, 30))
    assert change is not None
    assert change[0] == datetime(2026, 9, 25, 17, 0)
    assert change[1].name == "Peak"


def test_tariff_validation_rejects_slug_collisions():
    periods = [
        TariffPeriod("Day Rate", parse_time("00:00"), parse_time("12:00"), Decimal("0.30")),
        TariffPeriod("day-rate", parse_time("12:00"), parse_time("00:00"), Decimal("0.20")),
    ]
    assert "slug_collision" in validate_tariff_periods(periods)
