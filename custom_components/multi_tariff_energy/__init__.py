"""Multi Tariff Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import DATA_COORDINATOR, MultiTariffEnergyCoordinator
from .tariff import tariffs_from_config

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multi Tariff Energy from a config entry."""
    coordinator = MultiTariffEnergyCoordinator(\n        hass, entry, tariffs_from_config(entry.data)\n    )
    await coordinator.async_start()
    entry_data = {DATA_COORDINATOR: coordinator}
    hass.data.setdefault(entry.domain, {})[entry.entry_id] = entry_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[entry.domain].pop(entry.entry_id)[DATA_COORDINATOR]
        await coordinator.async_stop()
    return unloaded
