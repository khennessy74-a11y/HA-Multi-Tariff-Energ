"""Multi Tariff Energy integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import DATA_COORDINATOR, MultiTariffEnergyCoordinator

PLATFORMS: list[str] = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Multi Tariff Energy from a config entry."""
    coordinator = MultiTariffEnergyCoordinator(hass, entry)
    await coordinator.async_start()
    hass.data.setdefault(entry.domain, {})[entry.entry_id] = {\n        DATA_COORDINATOR: coordinator\n    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        coordinator = hass.data[entry.domain].pop(entry.entry_id)[DATA_COORDINATOR]
        await coordinator.async_stop()
    return unloaded
