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
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import slugify

from .coordinator import DATA_COORDINATOR, MultiTariffEnergyCoordinator


@dataclass(frozen=True, kw_only=True)
class MultiTariffSensorDescription(SensorEntityDescription):
    """Describe a Multi Tariff Energy sensor."""


ENERGY_KEYS = {
    "import_today": "Import Today",
    "export_today": "Export Today",
    "solar_today": "Solar Generation Today",
    "import_yesterday": "Import Yesterday",
    "export_yesterday": "Export Yesterday",
    "solar_yesterday": "Solar Generation Yesterday",
    "import_month": "Import Month",
    "export_month": "Export Month",
    "solar_month": "Solar Generation Month",
    "import_last_month": "Import Last Month",
    "export_last_month": "Export Last Month",
    "solar_last_month": "Solar Generation Last Month",
    "import_billing_cycle": "Import Billing Cycle",
    "export_billing_cycle": "Export Billing Cycle",
    "solar_billing_cycle": "Solar Generation Billing Cycle",
    "import_previous_billing_cycle": "Import Previous Billing Cycle",
    "export_previous_billing_cycle": "Export Previous Billing Cycle",
    "solar_previous_billing_cycle": "Solar Generation Previous Billing Cycle",
}

MONEY_KEYS = {
    "buy_cost_today": "Buy Cost Today",
    "export_credit_today": "Export Credit Today",
    "standing_charge_today": "Standing Charge Today",
    "vat_today": "VAT Today",
    "net_cost_today": "Net Cost Today",
    "buy_cost_yesterday": "Buy Cost Yesterday",
    "export_credit_yesterday": "Export Credit Yesterday",
    "standing_charge_yesterday": "Standing Charge Yesterday",
    "vat_yesterday": "VAT Yesterday",
    "net_cost_yesterday": "Net Cost Yesterday",
    "buy_cost_month": "Buy Cost Month",
    "export_credit_month": "Export Credit Month",
    "standing_charge_month": "Standing Charge Month",
    "vat_month": "VAT Month",
    "net_cost_month": "Net Cost Month",
    "buy_cost_last_month": "Buy Cost Last Month",
    "export_credit_last_month": "Export Credit Last Month",
    "standing_charge_last_month": "Standing Charge Last Month",
    "vat_last_month": "VAT Last Month",
    "net_cost_last_month": "Net Cost Last Month",
    "buy_cost_billing_cycle": "Buy Cost Billing Cycle",
    "export_credit_billing_cycle": "Export Credit Billing Cycle",
    "standing_charge_billing_cycle": "Standing Charge Billing Cycle",
    "vat_billing_cycle": "VAT Billing Cycle",
    "net_cost_billing_cycle": "Net Cost Billing Cycle",
    "buy_cost_previous_billing_cycle": "Buy Cost Previous Billing Cycle",
    "export_credit_previous_billing_cycle": "Export Credit Previous Billing Cycle",
    "standing_charge_previous_billing_cycle": "Standing Charge Previous Billing Cycle",
    "vat_previous_billing_cycle": "VAT Previous Billing Cycle",
    "net_cost_previous_billing_cycle": "Net Cost Previous Billing Cycle",
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
    descriptions = list(SENSOR_DESCRIPTIONS)
    for tariff_name in dict.fromkeys(period.name for period in coordinator.tariffs):
        slug = slugify(tariff_name)
        descriptions.extend(
            (
                MultiTariffSensorDescription(
                    key=f"tariff_{slug}_import_today",
                    name=f"{tariff_name} Import Today",
                    device_class=SensorDeviceClass.ENERGY,
                    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    state_class=SensorStateClass.TOTAL,
                ),
                MultiTariffSensorDescription(
                    key=f"tariff_{slug}_cost_today",
                    name=f"{tariff_name} Cost Today",
                    device_class=SensorDeviceClass.MONETARY,
                    state_class=SensorStateClass.TOTAL,
                ),
                MultiTariffSensorDescription(
                    key=f"tariff_{slug}_import_month",
                    name=f"{tariff_name} Import Month",
                    device_class=SensorDeviceClass.ENERGY,
                    native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    state_class=SensorStateClass.TOTAL,
                ),
                MultiTariffSensorDescription(
                    key=f"tariff_{slug}_cost_month",
                    name=f"{tariff_name} Cost Month",
                    device_class=SensorDeviceClass.MONETARY,
                    state_class=SensorStateClass.TOTAL,
                ),
            )
        )
    async_add_entities(
        MultiTariffEnergySensor(entry, coordinator, description)
        for description in descriptions
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
        self._attr_device_info = DeviceInfo(
            identifiers={("multi_tariff_energy", entry.entry_id)},
            name=entry.title,
            manufacturer="Multi Tariff Energy",
            model="Energy Accounting",
        )
        currency = entry.data.get("currency", "EUR")
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = currency
        elif description.key in {"current_rate", "next_rate"}:
            self._attr_native_unit_of_measurement = f"{currency}/kWh"

    async def async_added_to_hass(self) -> None:
        """Subscribe to accounting updates."""
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> Any:
        """Return the current accounting value."""
        return self.coordinator.value(self.entity_description.key)
