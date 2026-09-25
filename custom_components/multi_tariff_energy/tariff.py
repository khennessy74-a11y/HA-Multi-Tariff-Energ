"""Tariff schedule and cost calculation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal


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
