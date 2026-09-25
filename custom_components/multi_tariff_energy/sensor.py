"""Sensor platform for Multi Tariff Energy."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import (
    CONF_CURRENCY,
    CONF_EXPORT_ENERGY_ENTITY,
    CONF_EXPORT_RATE,
    CONF_IMPORT_ENERGY_ENTITY,
    CONF_STANDING_CHARGE,
    CONF_VAT_RATE,
)


@dataclass(frozen=True, kw_only=True)
class MultiTariffSensorDescription(SensorEntityDescription):
    """Describes a Multi Tariff Energy sensor."""


SENSOR_DESCRIPTIONS = (
    MultiTariffSensorDescription(
        key="import_energy_total",
        name="Import Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-import",
    ),
    MultiTariffSensorDescription(
        key="export_energy_total",
        name="Export Energy Total",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        icon="mdi:transmission-tower-export",
    ),
    MultiTariffSensorDescription(
        key="export_value_total",
        name="Export Value Total",
        icon="mdi:cash-plus",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Multi Tariff Energy sensors."""
    async_add_entities(
        MultiTariffEnergySensor(hass, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class MultiTariffEnergySensor(SensorEntity):
    """Representation of a Multi Tariff Energy sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        description: MultiTariffSensorDescription,
    ) -> None:
        self.hass = hass
        self.entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        if description.key == "export_value_total":
            self._attr_native_unit_of_measurement = entry.data.get(CONF_CURRENCY, "EUR")

    @staticmethod
    def _decimal_state(state: str | None) -> Decimal | None:
        if state is None:
            return None
        try:
            return Decimal(state)
        except (InvalidOperation, TypeError):
            return None

    @property
    def native_value(self) -> Any:
        key = self.entity_description.key

        if key == "import_energy_total":
            state = self.hass.states.get(self.entry.data[CONF_IMPORT_ENERGY_ENTITY])
            return self._decimal_state(state.state if state else None)

        if key == "export_energy_total":
            state = self.hass.states.get(self.entry.data[CONF_EXPORT_ENERGY_ENTITY])
            return self._decimal_state(state.state if state else None)

        if key == "export_value_total":
            state = self.hass.states.get(self.entry.data[CONF_EXPORT_ENERGY_ENTITY])
            energy = self._decimal_state(state.state if state else None)
            if energy is None:
                return None
            rate = Decimal(str(self.entry.data.get(CONF_EXPORT_RATE, 0)))
            return round(energy * rate, 4)

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose configured billing inputs while the cost engine is built."""
        return {
            "standing_charge": self.entry.data.get(CONF_STANDING_CHARGE, 0),
            "vat_rate": self.entry.data.get(CONF_VAT_RATE, 0),
        }
