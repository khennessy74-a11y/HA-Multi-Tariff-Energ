"""Runtime accounting coordinator for Multi Tariff Energy."""

from __future__ import annotations

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

from .accumulator import (
    AccountingState,
    accounting_state_from_storage,
    decimal_value,
)
from .const import (
    CONF_EXPORT_ENERGY_ENTITY,
    CONF_EXPORT_RATE,
    CONF_IMPORT_ENERGY_ENTITY,
    CONF_SOLAR_ENERGY_ENTITY,
    CONF_STANDING_CHARGE,
    CONF_VAT_RATE,
)
from .tariff import TariffPeriod, active_tariff

DATA_COORDINATOR = "coordinator"


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
        for entity_id in entity_ids:
            self._process_entity(entity_id)
        await self._async_save()

    async def async_stop(self) -> None:
        """Stop observing source sensors."""
        await self._async_save()
        if self._remove_midnight_listener is not None:
            self._remove_midnight_listener()
            self._remove_midnight_listener = None
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None

    def _apply_daily_charge(self) -> None:
        self.state.apply_standing_charge(
            dt_util.now().date(),
            Decimal(str(self.entry.data.get(CONF_STANDING_CHARGE, 0))),
            Decimal(str(self.entry.data.get(CONF_VAT_RATE, 0))),
        )

    @callback
    def _async_source_changed(self, event: Event) -> None:
        """Process a source meter state change."""
        self._apply_daily_charge()
        self._process_entity(event.data["entity_id"])
        self._notify_listeners()
        self.hass.async_create_task(self._async_save())

    def _process_entity(self, entity_id: str) -> None:
        source = self.hass.states.get(entity_id)
        current = decimal_value(source.state if source else None)
        if current is None:
            return

        if entity_id == self.entry.data[CONF_IMPORT_ENERGY_ENTITY]:
            delta = self.state.import_meter.update(current)
            tariff = active_tariff(self.tariffs, dt_util.now())
            if tariff is not None:
                self.state.today.add_import(tariff.name, delta, tariff.rate)
                self.state.month_totals.add_import(
                    tariff.name, delta, tariff.rate
                )
            return

        if entity_id == self.entry.data[CONF_EXPORT_ENERGY_ENTITY]:
            delta = self.state.export_meter.update(current)
            rate = Decimal(str(self.entry.data.get(CONF_EXPORT_RATE, 0)))
            self.state.today.add_export(delta, rate)
            self.state.month_totals.add_export(delta, rate)
            return

        if entity_id == self.entry.data.get(CONF_SOLAR_ENERGY_ENTITY):
            delta = self.state.solar_meter.update(current)
            self.state.today.add_solar(delta)
            self.state.month_totals.add_solar(delta)

    async def _async_save(self) -> None:
        """Persist accounting state."""
        await self._store.async_save(self.state.as_storage_dict())

    def value(self, key: str) -> Any:
        """Return a runtime sensor value."""
        today = self.state.today
        month = self.state.month_totals
        values = {
            "import_today": today.import_kwh,
            "export_today": today.export_kwh,
            "solar_today": today.solar_kwh,
            "buy_cost_today": today.import_cost,
            "export_credit_today": today.export_credit,
            "standing_charge_today": today.standing_charge,
            "vat_today": today.vat,
            "net_cost_today": today.net_cost,
            "import_month": month.import_kwh,
            "export_month": month.export_kwh,
            "solar_month": month.solar_kwh,
            "buy_cost_month": month.import_cost,
            "export_credit_month": month.export_credit,
            "standing_charge_month": month.standing_charge,
            "vat_month": month.vat,
            "net_cost_month": month.net_cost,
        }
        return values.get(key)
