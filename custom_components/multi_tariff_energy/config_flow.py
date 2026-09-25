"""Config flow for Multi Tariff Energy."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_BILLING_DAY,
    CONF_CURRENCY,
    CONF_EXPORT_ENERGY_ENTITY,
    CONF_EXPORT_RATE,
    CONF_IMPORT_ENERGY_ENTITY,
    CONF_RATES_INCLUDE_VAT,
    CONF_SOLAR_ENERGY_ENTITY,
    CONF_STANDING_CHARGE,
    CONF_VAT_ON_IMPORT,
    CONF_VAT_ON_STANDING_CHARGE,
    CONF_VAT_RATE,
    DEFAULT_BILLING_DAY,
    DEFAULT_CURRENCY,
    DEFAULT_EXPORT_RATE,
    DEFAULT_NAME,
    DEFAULT_RATES_INCLUDE_VAT,
    DEFAULT_STANDING_CHARGE,
    DEFAULT_VAT_ON_IMPORT,
    DEFAULT_VAT_ON_STANDING_CHARGE,
    DEFAULT_VAT_RATE,
    DOMAIN,
)
from .tariff import TariffPeriod, parse_time, validate_tariff_periods

CONF_TARIFF_WINDOWS = "tariff_windows"
CONF_TARIFF_NAME = "tariff_name"
CONF_TARIFF_START = "tariff_start"
CONF_TARIFF_END = "tariff_end"
CONF_TARIFF_RATE = "tariff_rate"
CONF_ADD_ANOTHER = "add_another"


class MultiTariffEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multi Tariff Energy."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return MultiTariffEnergyOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._base_data: dict[str, Any] = {}
        self._tariff_windows: list[dict[str, Any]] = []

    async def async_step_user(self, user_input=None):
        """Collect source sensors and billing settings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._base_data = dict(user_input)
            return await self.async_step_tariff()

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_IMPORT_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Required(CONF_EXPORT_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Optional(CONF_SOLAR_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Required(
                    CONF_STANDING_CHARGE, default=DEFAULT_STANDING_CHARGE
                ): vol.Coerce(float),
                vol.Required(CONF_VAT_RATE, default=DEFAULT_VAT_RATE): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
                vol.Required(
                    CONF_RATES_INCLUDE_VAT, default=DEFAULT_RATES_INCLUDE_VAT
                ): bool,
                vol.Required(
                    CONF_VAT_ON_IMPORT, default=DEFAULT_VAT_ON_IMPORT
                ): bool,
                vol.Required(
                    CONF_VAT_ON_STANDING_CHARGE,
                    default=DEFAULT_VAT_ON_STANDING_CHARGE,
                ): bool,
                vol.Required(CONF_EXPORT_RATE, default=DEFAULT_EXPORT_RATE): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
                vol.Required(CONF_CURRENCY, default=DEFAULT_CURRENCY): str,
                vol.Required(CONF_BILLING_DAY, default=DEFAULT_BILLING_DAY): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=28)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _tariff_schema(self) -> vol.Schema:
        """Return the schema for one tariff window."""
        return vol.Schema(
            {
                vol.Required(CONF_TARIFF_NAME): str,
                vol.Required(CONF_TARIFF_START): str,
                vol.Required(CONF_TARIFF_END): str,
                vol.Required(CONF_TARIFF_RATE): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
                vol.Required(CONF_ADD_ANOTHER, default=False): bool,
            }
        )

    async def async_step_tariff(self, user_input=None):
        """Add one tariff time window at a time."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input[CONF_TARIFF_NAME].strip()
            start = user_input[CONF_TARIFF_START]
            end = user_input[CONF_TARIFF_END]
            if not name:
                errors["base"] = "tariff_name_required"
                return self.async_show_form(
                    step_id="tariff",
                    data_schema=self._tariff_schema(),
                    errors=errors,
                    description_placeholders={
                        "count": str(len(self._tariff_windows) + 1),
                    },
                )
            try:
                parse_time(start)
                parse_time(end)
            except (TypeError, ValueError):
                errors["base"] = "invalid_tariff_time"
                return self.async_show_form(
                    step_id="tariff",
                    data_schema=self._tariff_schema(),
                    errors=errors,
                    description_placeholders={
                        "count": str(len(self._tariff_windows) + 1),
                    },
                )
            if start == end:
                errors["base"] = "tariff_start_equals_end"
            else:
                self._tariff_windows.append(
                    {
                        "name": name,
                        "start": start,
                        "end": end,
                        "rate": user_input[CONF_TARIFF_RATE],
                    }
                )
                if user_input[CONF_ADD_ANOTHER]:
                    return await self.async_step_tariff()

                periods = [
                    TariffPeriod(
                        name=str(window["name"]),
                        start=parse_time(str(window["start"])),
                        end=parse_time(str(window["end"])),
                        rate=Decimal(str(window["rate"])),
                    )
                    for window in self._tariff_windows
                ]
                schedule_errors = validate_tariff_periods(periods)
                if schedule_errors:
                    self._tariff_windows.pop()
                    errors["base"] = f"tariff_schedule_{schedule_errors[0]}"
                else:
                    data = dict(self._base_data)
                    data[CONF_TARIFF_WINDOWS] = self._tariff_windows
                    return self.async_create_entry(
                        title=data[CONF_NAME],
                        data=data,
                    )

        schema = self._tariff_schema()
        return self.async_show_form(
            step_id="tariff",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "count": str(len(self._tariff_windows) + 1),
            },
        )



class MultiTariffEnergyOptionsFlow(config_entries.OptionsFlow):
    """Handle editable billing options."""

    def __init__(self, config_entry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._options_base_data: dict[str, Any] = {}
        self._options_tariff_windows: list[dict[str, Any]] = []

    async def async_step_init(self, user_input=None):
        """Edit billing settings without recreating the integration."""
        if user_input is not None:
            self._options_base_data = dict(user_input)
            self._options_tariff_windows = []
            return await self.async_step_tariff()

        data = self.config_entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_IMPORT_ENERGY_ENTITY,
                    default=data.get(CONF_IMPORT_ENERGY_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Required(
                    CONF_EXPORT_ENERGY_ENTITY,
                    default=data.get(CONF_EXPORT_ENERGY_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Optional(
                    CONF_SOLAR_ENERGY_ENTITY,
                    default=data.get(CONF_SOLAR_ENERGY_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="energy")
                ),
                vol.Required(
                    CONF_STANDING_CHARGE,
                    default=data.get(CONF_STANDING_CHARGE, DEFAULT_STANDING_CHARGE),
                ): vol.Coerce(float),
                vol.Required(
                    CONF_VAT_RATE, default=data.get(CONF_VAT_RATE, DEFAULT_VAT_RATE)
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Required(
                    CONF_RATES_INCLUDE_VAT,
                    default=data.get(CONF_RATES_INCLUDE_VAT, DEFAULT_RATES_INCLUDE_VAT),
                ): bool,
                vol.Required(
                    CONF_VAT_ON_IMPORT,
                    default=data.get(CONF_VAT_ON_IMPORT, DEFAULT_VAT_ON_IMPORT),
                ): bool,
                vol.Required(
                    CONF_VAT_ON_STANDING_CHARGE,
                    default=data.get(
                        CONF_VAT_ON_STANDING_CHARGE,
                        DEFAULT_VAT_ON_STANDING_CHARGE,
                    ),
                ): bool,
                vol.Required(
                    CONF_EXPORT_RATE,
                    default=data.get(CONF_EXPORT_RATE, DEFAULT_EXPORT_RATE),
                ): vol.All(vol.Coerce(float), vol.Range(min=0)),
                vol.Required(
                    CONF_CURRENCY, default=data.get(CONF_CURRENCY, DEFAULT_CURRENCY)
                ): str,
                vol.Required(
                    CONF_BILLING_DAY,
                    default=data.get(CONF_BILLING_DAY, DEFAULT_BILLING_DAY),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=28)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)


    async def async_step_tariff(self, user_input=None):
        """Replace the tariff schedule one window at a time."""
        errors: dict[str, str] = {}
        if user_input is not None:
            name = user_input[CONF_TARIFF_NAME].strip()
            start = user_input[CONF_TARIFF_START]
            end = user_input[CONF_TARIFF_END]
            if not name:
                errors["base"] = "tariff_name_required"
            else:
                try:
                    parse_time(start)
                    parse_time(end)
                except (TypeError, ValueError):
                    errors["base"] = "invalid_tariff_time"
                if not errors and start == end:
                    errors["base"] = "tariff_start_equals_end"
            if not errors:
                self._options_tariff_windows.append(
                    {
                        "name": name,
                        "start": start,
                        "end": end,
                        "rate": user_input[CONF_TARIFF_RATE],
                    }
                )
                if user_input[CONF_ADD_ANOTHER]:
                    return await self.async_step_tariff()
                periods = [
                    TariffPeriod(
                        name=str(window["name"]),
                        start=parse_time(str(window["start"])),
                        end=parse_time(str(window["end"])),
                        rate=Decimal(str(window["rate"])),
                    )
                    for window in self._options_tariff_windows
                ]
                schedule_errors = validate_tariff_periods(periods)
                if schedule_errors:
                    self._options_tariff_windows.pop()
                    errors["base"] = f"tariff_schedule_{schedule_errors[0]}"
                else:
                    new_data = dict(self.config_entry.data)
                    new_data.update(self._options_base_data)
                    new_data[CONF_TARIFF_WINDOWS] = self._options_tariff_windows
                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data
                    )
                    await self.hass.config_entries.async_reload(
                        self.config_entry.entry_id
                    )
                    return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="tariff",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TARIFF_NAME): str,
                    vol.Required(CONF_TARIFF_START): str,
                    vol.Required(CONF_TARIFF_END): str,
                    vol.Required(CONF_TARIFF_RATE): vol.All(
                        vol.Coerce(float), vol.Range(min=0)
                    ),
                    vol.Required(CONF_ADD_ANOTHER, default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "count": str(len(self._options_tariff_windows) + 1),
            },
        )
