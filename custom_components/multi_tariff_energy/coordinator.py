"""Runtime accounting coordinator for Multi Tariff Energy."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .accumulator import (
    AccountingState,
    accounting_state_from_storage,
    decimal_value,
)
from .const import (
    CONF_BILLING_DAY,
    CONF_EXPORT_ENERGY_ENTITY,
    CONF_EXPORT_RATE,
    CONF_IMPORT_ENERGY_ENTITY,
    CONF_RATES_INCLUDE_VAT,
    CONF_SOLAR_ENERGY_ENTITY,
    CONF_STANDING_CHARGE,
    CONF_VAT_ON_IMPORT,
    CONF_VAT_ON_STANDING_CHARGE,
    CONF_VAT_RATE,
)
from .tariff import TariffPeriod, active_tariff, next_tariff_change

DATA_COORDINATOR = "coordinator"

_ENERGY_TO_KWH = {
    "Wh": Decimal("0.001"),
    "kWh": Decimal("1"),
    "MWh": Decimal("1000"),
    "GWh": Decimal("1000000"),
}


def energy_value_kwh(value: str | None, unit: str | None) -> Decimal | None:
    """Normalize a cumulative energy reading to kWh without float rounding."""
    current = decimal_value(value)
    if current is None:
        return None
    if unit is None:
        return current
    factor = _ENERGY_TO_KWH.get(unit)
    if factor is None:
        return None
    return current * factor


class MultiTariffEnergyCoordinator:
    """Observe cumulative energy sensors and maintain accounting totals."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        tariffs: list[TariffPeriod] | None = None,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.tariffs = tariffs or []
        self.state = AccountingState.create(dt_util.now().date())
        self._remove_listener = None
        self._remove_midnight_listener = None
        self._remove_tariff_listeners: list = []
        self._listeners: list = []
        self._store: Store[dict[str, Any]] = Store(
            hass, 1, f"multi_tariff_energy.{entry.entry_id}"
        )

    @callback
    def async_add_listener(self, listener) -> callable:
        """Register a listener for accounting value changes."""
        self._listeners.append(listener)

        def remove_listener() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return remove_listener

    @callback
    def _notify_listeners(self) -> None:
        """Notify entities that accounting values changed."""
        for listener in list(self._listeners):
            listener()

    async def async_start(self) -> None:
        """Start observing configured source sensors."""
        stored = await self._store.async_load()
        if stored:
            self.state = accounting_state_from_storage(stored)
        self.state.sync_source_entities(
            self.entry.data[CONF_IMPORT_ENERGY_ENTITY],
            self.entry.data[CONF_EXPORT_ENERGY_ENTITY],
            self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY),
        )
        self._apply_daily_charge()
        entity_ids = [
            self.entry.data[CONF_IMPORT_ENERGY_ENTITY],
            self.entry.data[CONF_EXPORT_ENERGY_ENTITY],
        ]
        solar = self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY)
        if solar:
            entity_ids.append(solar)
        self._remove_midnight_listener = async_track_time_change(
            self.hass, self._async_midnight, hour=0, minute=0, second=0
        )
        self._remove_listener = async_track_state_change_event(
            self.hass, entity_ids, self._async_source_changed
        )
        boundary_times = {
            (period.start.hour, period.start.minute) for period in self.tariffs
        }
        for hour, minute in boundary_times:
            self._remove_tariff_listeners.append(
                async_track_time_change(
                    self.hass,
                    self._async_tariff_boundary,
                    hour=hour,
                    minute=minute,
                    second=0,
                )
            )
        for entity_id in entity_ids:
            self._process_entity(entity_id)
        await self._async_save()

    async def async_stop(self) -> None:
        """Stop observing source sensors."""
        await self._async_save()
        if self._remove_midnight_listener is not None:
            self._remove_midnight_listener()
            self._remove_midnight_listener = None
        for remove_listener in self._remove_tariff_listeners:
            remove_listener()
        self._remove_tariff_listeners.clear()
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    @callback
    def _async_midnight(self, now) -> None:
        """Snapshot source meters before rolling over to a new local day."""
        import_entity = self.entry.data[CONF_IMPORT_ENERGY_ENTITY]
        previous_tariff = active_tariff(
            self.tariffs, now - timedelta(microseconds=1)
        )
        self._process_entity(import_entity, tariff_override=previous_tariff)

        export_entity = self.entry.data[CONF_EXPORT_ENERGY_ENTITY]
        self._process_entity(export_entity)

        solar_entity = self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY)
        if solar_entity:
            self._process_entity(solar_entity)

        self._apply_daily_charge()
        self._notify_listeners()
        self.hass.async_create_task(self._async_save())

    @callback
    def _async_tariff_boundary(self, now) -> None:
        """Snapshot source meters before switching to the new tariff window."""
        self._apply_daily_charge()
        import_entity = self.entry.data[CONF_IMPORT_ENERGY_ENTITY]
        previous_tariff = active_tariff(
            self.tariffs, now - timedelta(microseconds=1)
        )
        self._process_entity(import_entity, tariff_override=previous_tariff)
        self._notify_listeners()
        self.hass.async_create_task(self._async_save())

    def _apply_daily_charge(self) -> None:
        today = dt_util.now().date()
        self.state.rollover_billing_cycle(
            today, int(self.entry.data.get(CONF_BILLING_DAY, 1))
        )
        self.state.apply_standing_charge(
            today,
            Decimal(str(self.entry.data.get(CONF_STANDING_CHARGE, 0))),
            Decimal(str(self.entry.data.get(CONF_VAT_RATE, 0))),
            bool(self.entry.data.get(CONF_VAT_ON_STANDING_CHARGE, True)),
        )

    @callback
    def _async_source_changed(self, event: Event) -> None:
        """Process a source meter state change."""
        self._apply_daily_charge()
        self._process_entity(event.data["entity_id"])
        self._notify_listeners()
        self.hass.async_create_task(self._async_save())

    def _process_entity(
        self, entity_id: str, tariff_override: TariffPeriod | None = None
    ) -> None:
        source = self.hass.states.get(entity_id)
        current = energy_value_kwh(
            source.state if source else None,
            source.attributes.get("unit_of_measurement") if source else None,
        )
        if current is None:
            return

        if entity_id == self.entry.data[CONF_IMPORT_ENERGY_ENTITY]:
            delta = self.state.import_meter.update(current)
            tariff = tariff_override or active_tariff(self.tariffs, dt_util.now())
            if tariff is not None:
                vat_rate = Decimal(str(self.entry.data.get(CONF_VAT_RATE, 0)))
                rate_includes_vat = bool(
                    self.entry.data.get(CONF_RATES_INCLUDE_VAT, False)
                )
                vat_applies = bool(self.entry.data.get(CONF_VAT_ON_IMPORT, True))
                self.state.today.add_import(
                    tariff.name,
                    delta,
                    tariff.rate,
                    vat_rate,
                    rate_includes_vat,
                    vat_applies,
                )
                self.state.billing_cycle.add_import(
                    tariff.name,
                    delta,
                    tariff.rate,
                    vat_rate,
                    rate_includes_vat,
                    vat_applies,
                )
                self.state.month_totals.add_import(
                    tariff.name,
                    delta,
                    tariff.rate,
                    vat_rate,
                    rate_includes_vat,
                    vat_applies,
                )
            return

        if entity_id == self.entry.data[CONF_EXPORT_ENERGY_ENTITY]:
            delta = self.state.export_meter.update(current)
            rate = Decimal(str(self.entry.data.get(CONF_EXPORT_RATE, 0)))
            self.state.today.add_export(delta, rate)
            self.state.month_totals.add_export(delta, rate)
            self.state.billing_cycle.add_export(delta, rate)
            return

        if entity_id == self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY):
            delta = self.state.solar_meter.update(current)
            self.state.today.add_solar(delta)
            self.state.month_totals.add_solar(delta)
            self.state.billing_cycle.add_solar(delta)

    async def async_snapshot_sources(self) -> None:
        """Account for current source readings before configuration changes."""
        self._apply_daily_charge()
        entity_ids = [
            self.entry.data[CONF_IMPORT_ENERGY_ENTITY],
            self.entry.data[CONF_EXPORT_ENERGY_ENTITY],
        ]
        solar = self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY)
        if solar:
            entity_ids.append(solar)
        for entity_id in entity_ids:
            self._process_entity(entity_id)
        await self._async_save()

    async def _async_save(self) -> None:
        """Persist accounting state."""
        await self._store.async_save(self.state.as_storage_dict())

    def value(self, key: str) -> Any:
        """Return a runtime sensor value."""
        today = self.state.today
        yesterday = self.state.yesterday
        month = self.state.month_totals
        last_month = self.state.last_month
        billing = self.state.billing_cycle
        previous_billing = self.state.previous_billing_cycle
        now = dt_util.now()
        current_tariff = active_tariff(self.tariffs, now)
        next_change = next_tariff_change(self.tariffs, now)
        values = {
            "current_tariff": current_tariff.name if current_tariff else None,
            "current_rate": current_tariff.rate if current_tariff else None,
            "next_tariff": next_change[1].name if next_change else None,
            "next_rate": next_change[1].rate if next_change else None,
            "next_rate_change": next_change[0] if next_change else None,
            "import_today": today.import_kwh,
            "export_today": today.export_kwh,
            "solar_today": today.solar_kwh,
            "buy_cost_today": today.import_cost,
            "export_credit_today": today.export_credit,
            "standing_charge_today": today.standing_charge,
            "vat_today": today.vat,
            "net_cost_today": today.net_cost,
            "import_yesterday": yesterday.import_kwh,
            "export_yesterday": yesterday.export_kwh,
            "solar_yesterday": yesterday.solar_kwh,
            "buy_cost_yesterday": yesterday.import_cost,
            "export_credit_yesterday": yesterday.export_credit,
            "standing_charge_yesterday": yesterday.standing_charge,
            "vat_yesterday": yesterday.vat,
            "net_cost_yesterday": yesterday.net_cost,
            "import_month": month.import_kwh,
            "export_month": month.export_kwh,
            "solar_month": month.solar_kwh,
            "buy_cost_month": month.import_cost,
            "export_credit_month": month.export_credit,
            "standing_charge_month": month.standing_charge,
            "vat_month": month.vat,
            "net_cost_month": month.net_cost,
            "import_last_month": last_month.import_kwh,
            "export_last_month": last_month.export_kwh,
            "solar_last_month": last_month.solar_kwh,
            "buy_cost_last_month": last_month.import_cost,
            "export_credit_last_month": last_month.export_credit,
            "standing_charge_last_month": last_month.standing_charge,
            "vat_last_month": last_month.vat,
            "net_cost_last_month": last_month.net_cost,
            "import_billing_cycle": billing.import_kwh,
            "export_billing_cycle": billing.export_kwh,
            "solar_billing_cycle": billing.solar_kwh,
            "buy_cost_billing_cycle": billing.import_cost,
            "export_credit_billing_cycle": billing.export_credit,
            "standing_charge_billing_cycle": billing.standing_charge,
            "vat_billing_cycle": billing.vat,
            "net_cost_billing_cycle": billing.net_cost,
            "import_previous_billing_cycle": previous_billing.import_kwh,
            "export_previous_billing_cycle": previous_billing.export_kwh,
            "solar_previous_billing_cycle": previous_billing.solar_kwh,
            "buy_cost_previous_billing_cycle": previous_billing.import_cost,
            "export_credit_previous_billing_cycle": previous_billing.export_credit,
            "standing_charge_previous_billing_cycle": previous_billing.standing_charge,
            "vat_previous_billing_cycle": previous_billing.vat,
            "net_cost_previous_billing_cycle": previous_billing.net_cost,
        }
        for tariff_name in dict.fromkeys(period.name for period in self.tariffs):
            slug = slugify(tariff_name)
            values[f"tariff_{slug}_import_today"] = today.tariff_import_kwh.get(
                tariff_name, Decimal("0")
            )
            values[f"tariff_{slug}_cost_today"] = today.tariff_import_cost.get(
                tariff_name, Decimal("0")
            )
            values[f"tariff_{slug}_import_month"] = month.tariff_import_kwh.get(
                tariff_name, Decimal("0")
            )
            values[f"tariff_{slug}_cost_month"] = month.tariff_import_cost.get(
                tariff_name, Decimal("0")
            )
        return values.get(key)
