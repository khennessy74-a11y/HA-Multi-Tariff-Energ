"""Persistent energy delta accumulator for Multi Tariff Energy."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

ZERO = Decimal("0")


def decimal_value(value: Any) -> Decimal | None:
    """Convert a value to Decimal, returning None for invalid states."""
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


@dataclass
class PeriodTotals:
    """Energy and money accumulated for one accounting period."""

    import_kwh: Decimal = ZERO
    export_kwh: Decimal = ZERO
    solar_kwh: Decimal = ZERO
    import_cost: Decimal = ZERO
    export_credit: Decimal = ZERO
    standing_charge: Decimal = ZERO
    vat: Decimal = ZERO
    tariff_import_kwh: dict[str, Decimal] = field(default_factory=dict)
    tariff_import_cost: dict[str, Decimal] = field(default_factory=dict)

    @property
    def net_cost(self) -> Decimal:
        """Return net cost after export credit."""
        return self.import_cost + self.standing_charge + self.vat - self.export_credit

    def add_import(self, tariff: str, delta: Decimal, rate: Decimal) -> None:
        """Add imported energy at a tariff rate."""
        if delta <= ZERO:
            return
        cost = delta * rate
        self.import_kwh += delta
        self.import_cost += cost
        self.tariff_import_kwh[tariff] = (
            self.tariff_import_kwh.get(tariff, ZERO) + delta
        )
        self.tariff_import_cost[tariff] = (
            self.tariff_import_cost.get(tariff, ZERO) + cost
        )

    def add_export(self, delta: Decimal, rate: Decimal) -> None:
        """Add exported energy and its credit."""
        if delta <= ZERO:
            return
        self.export_kwh += delta
        self.export_credit += delta * rate

    def add_solar(self, delta: Decimal) -> None:
        """Add solar generation."""
        if delta > ZERO:
            self.solar_kwh += delta


@dataclass
class MeterTracker:
    """Track a cumulative source meter and return safe positive deltas."""

    last_value: Decimal | None = None

    def update(self, current: Decimal | None) -> Decimal:
        """Update a cumulative meter.

        A first reading establishes the baseline. A lower reading is treated
        as a meter reset and also establishes a new baseline without creating
        artificial consumption.
        """
        if current is None:
            return ZERO
        previous = self.last_value
        self.last_value = current
        if previous is None or current < previous:
            return ZERO
        return current - previous


@dataclass
class AccountingState:
    """State persisted by the integration."""

    day: str
    month: str
    today: PeriodTotals = field(default_factory=PeriodTotals)
    month_totals: PeriodTotals = field(default_factory=PeriodTotals)
    import_meter: MeterTracker = field(default_factory=MeterTracker)
    export_meter: MeterTracker = field(default_factory=MeterTracker)
    solar_meter: MeterTracker = field(default_factory=MeterTracker)
    standing_charge_applied_day: str | None = None

    @classmethod
    def create(cls, today: date) -> AccountingState:
        """Create an empty accounting state."""
        return cls(day=today.isoformat(), month=today.strftime("%Y-%m"))

    def rollover(self, today: date) -> None:
        """Roll daily/monthly counters when the local calendar changes."""
        day_key = today.isoformat()
        month_key = today.strftime("%Y-%m")
        if self.day != day_key:
            self.today = PeriodTotals()
            self.day = day_key
        if self.month != month_key:
            self.month_totals = PeriodTotals()
            self.month = month_key

    def apply_standing_charge(
        self,
        today: date,
        charge: Decimal,
        vat_percent: Decimal,
    ) -> None:
        """Apply the standing charge exactly once per local calendar day."""
        self.rollover(today)
        day_key = today.isoformat()
        if self.standing_charge_applied_day == day_key:
            return
        vat = charge * vat_percent / Decimal("100")
        for totals in (self.today, self.month_totals):
            totals.standing_charge += charge
            totals.vat += vat
        self.standing_charge_applied_day = day_key

    def as_storage_dict(self) -> dict[str, Any]:
        """Serialize state using strings for exact Decimal persistence."""
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value)
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value

        return convert(asdict(self))



def _period_totals_from_dict(data: dict[str, Any]) -> PeriodTotals:
    """Restore period totals from storage."""
    scalar_fields = (
        "import_kwh",
        "export_kwh",
        "solar_kwh",
        "import_cost",
        "export_credit",
        "standing_charge",
        "vat",
    )
    kwargs = {
        field_name: Decimal(str(data.get(field_name, "0")))
        for field_name in scalar_fields
    }
    kwargs["tariff_import_kwh"] = {
        str(key): Decimal(str(value))
        for key, value in data.get("tariff_import_kwh", {}).items()
    }
    kwargs["tariff_import_cost"] = {
        str(key): Decimal(str(value))
        for key, value in data.get("tariff_import_cost", {}).items()
    }
    return PeriodTotals(**kwargs)


def accounting_state_from_storage(data: dict[str, Any]) -> AccountingState:
    """Restore exact accounting state persisted by as_storage_dict."""
    return AccountingState(
        day=str(data["day"]),
        month=str(data["month"]),
        today=_period_totals_from_dict(data.get("today", {})),
        month_totals=_period_totals_from_dict(data.get("month_totals", {})),
        import_meter=MeterTracker(
            decimal_value(data.get("import_meter", {}).get("last_value"))
        ),
        export_meter=MeterTracker(
            decimal_value(data.get("export_meter", {}).get("last_value"))
        ),
        solar_meter=MeterTracker(
            decimal_value(data.get("solar_meter", {}).get("last_value"))
        ),
        standing_charge_applied_day=data.get("standing_charge_applied_day"),
    )
