"""Sensor platform for Multi Tariff Energy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import DATA_COORDINATOR, MultiTariffEnergyCoordinator


@dataclass(frozen=True, kw_only=True)
class MultiTariffSensorDescription(SensorEntityDescription):
    """Describe a Multi Tariff Energy sensor."""


ENERGY_KEYS = {
    "import_today": "Import Today",
    "export_today": "Export Today",
    "solar_today": "Solar Generation Today",
    "import_month": "Import Month",
    "export_month": "Export Month",
    "solar_month": "Solar Generation Month",
}

MONEY_KEYS = {
    "buy_cost_today": "Buy Cost Today",
    "export_credit_today": "Export Credit Today",
    "standing_charge_today": "Standing Charge Today",
    "vat_today": "VAT Today",
    "net_cost_today": "Net Cost Today",
    "buy_cost_month": "Buy Cost Month",
    "export_credit_month": "Export Credit Month",
    "standing_charge_month": "Standing Charge Month",
    "vat_month": "VAT Month",
    "net_cost_month": "Net Cost Month",
}

INFO_DESCRIPTIONS = (
    MultiTariffSensorDescription(key="current_tariff", name="Current Tariff"),
    MultiTariffSensorDescription(key="current_rate", name="Current Rate"),
    MultiTariffSensorDescription(key="next_tariff", name="Next Tariff"),
    MultiTariffSensorDescription(key="next_rate", name="Next Rate"),
    MultiTariffSensorDescription(
        key="next_rate_change",
        name="Next Rate Change",
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
)

SENSOR_DESCRIPTIONS = INFO_DESCRIPTIONS + tuple(
    MultiTariffSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.TOTAL,
    )
    for key, name in ENERGY_KEYS.items()
) + tuple(
    MultiTariffSensorDescription(
        key=key,
        name=name,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    )
    for key, name in MONEY_KEYS.items()
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Multi Tariff Energy sensors."""
    coordinator: MultiTariffEnergyCoordinator = hass.data[entry.domain][
        entry.entry_id
    ][DATA_COORDINATOR]
    async_add_entities(
        MultiTariffEnergySensor(entry, coordinator, description)
        for description in SENSOR_DESCRIPTIONS
    )


class MultiTariffEnergySensor(SensorEntity):
    """Expose a value from the accounting coordinator."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        coordinator: MultiTariffEnergyCoordinator,
        description: MultiTariffSensorDescription,
    ) -> None:
        self.entry = entry
        self.coordinator = coordinator
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = entry.data.get(
                "currency", "EUR"
            )

    async def async_added_to_hass(self) -> None:
        """Subscribe to accounting updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> Any:
        """Return the current accounting value."""
        return self.coordinator.value(self.entity_description.key)
