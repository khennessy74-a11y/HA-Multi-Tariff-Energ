"""Config flow for Multi Tariff Energy."""

from __future__ import annotations

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
    CONF_SOLAR_ENERGY_ENTITY,
    CONF_STANDING_CHARGE,
    CONF_VAT_RATE,
    DEFAULT_BILLING_DAY,
    DEFAULT_CURRENCY,
    DEFAULT_EXPORT_RATE,
    DEFAULT_NAME,
    DEFAULT_STANDING_CHARGE,
    DEFAULT_VAT_RATE,
    DOMAIN,
)


class MultiTariffEnergyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Multi Tariff Energy."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_IMPORT_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(CONF_EXPORT_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_SOLAR_ENERGY_ENTITY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_STANDING_CHARGE, default=DEFAULT_STANDING_CHARGE
                ): vol.Coerce(float),
                vol.Required(CONF_VAT_RATE, default=DEFAULT_VAT_RATE): vol.All(
                    vol.Coerce(float), vol.Range(min=0)
                ),
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
