"""Tariff schedule and cost calculation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from decimal import Decimal

from homeassistant.util import slugify


@dataclass(frozen=True)
class TariffPeriod:
    """One repeating daily import tariff period."""

    name: str
    start: time
    end: time
    rate: Decimal

    def active_at(self, when: datetime) -> bool:
        """Return whether this period is active at a local datetime."""
        current = when.time().replace(tzinfo=None)
        if self.start < self.end:
            return self.start <= current < self.end
        return current >= self.start or current < self.end


def parse_time(value: str) -> time:
    """Parse an HH:MM time value."""
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour=hour, minute=minute)


def active_tariff(
    periods: list[TariffPeriod], when: datetime
) -> TariffPeriod | None:
    """Return the active tariff period."""
    return next((period for period in periods if period.active_at(when)), None)


def energy_cost(energy_kwh: Decimal, rate: Decimal) -> Decimal:
    """Calculate an energy charge."""
    return energy_kwh * rate


def gross_cost(
    import_cost: Decimal,
    standing_charge: Decimal,
    vat_percent: Decimal,
) -> Decimal:
    """Calculate gross cost including standing charge and VAT."""
    subtotal = import_cost + standing_charge
    return subtotal * (Decimal("1") + vat_percent / Decimal("100"))


def net_cost(gross_import_cost: Decimal, export_credit: Decimal) -> Decimal:
    """Calculate net electricity cost after export credit."""
    return gross_import_cost - export_credit




def tariffs_from_config(data: dict[str, object]) -> list[TariffPeriod]:
    """Build tariff windows from config entry data.

    A tariff name may appear in multiple windows. This lets one logical rate,
    such as Day, cover several separate periods while accounting totals are
    still grouped under the same tariff name.
    """
    raw_windows = data.get("tariff_windows", [])
    if not isinstance(raw_windows, list):
        return []

    periods: list[TariffPeriod] = []
    for window in raw_windows:
        if not isinstance(window, dict):
            continue
        name = window.get("name")
        start = window.get("start")
        end = window.get("end")
        rate = window.get("rate")
        if not all(value is not None for value in (name, start, end, rate)):
            continue
        periods.append(
            TariffPeriod(
                name=str(name),
                start=parse_time(str(start)),
                end=parse_time(str(end)),
                rate=Decimal(str(rate)),
            )
        )
    return periods



def validate_tariff_periods(periods: list[TariffPeriod]) -> list[str]:
    """Return validation errors for overlapping or uncovered tariff minutes."""
    if not periods:
        return ["no_tariffs"]

    coverage: list[str | None] = [None] * (24 * 60)
    errors: set[str] = set()

    for period in periods:
        start = period.start.hour * 60 + period.start.minute
        end = period.end.hour * 60 + period.end.minute
        if start == end:
            errors.add("zero_length")
            continue

        minutes = (
            range(start, end)
            if start < end
            else list(range(start, 24 * 60)) + list(range(0, end))
        )
        for minute in minutes:
            if coverage[minute] is not None:
                errors.add("overlap")
            coverage[minute] = period.name

    if any(value is None for value in coverage):
        errors.add("gap")

    slug_names: dict[str, str] = {}
    for period in periods:
        slug = slugify(period.name)
        existing = slug_names.get(slug)
        if existing is not None and existing != period.name:
            errors.add("slug_collision")
        else:
            slug_names[slug] = period.name

    return sorted(errors)



def next_tariff_change(
    periods: list[TariffPeriod], when: datetime
) -> tuple[datetime, TariffPeriod] | None:
    """Return the next local tariff boundary and tariff active after it."""
    if not periods:
        return None

    current = active_tariff(periods, when)
    for minutes_ahead in range(1, 24 * 60 + 1):
        candidate = when.replace(second=0, microsecond=0)
        candidate += timedelta(minutes=minutes_ahead)
        candidate_tariff = active_tariff(periods, candidate)
        if candidate_tariff is not None:
            current_identity = (current.name, current.rate) if current else None
            candidate_identity = (candidate_tariff.name, candidate_tariff.rate)
            if candidate_identity != current_identity:
                return candidate, candidate_tariff
    return None
