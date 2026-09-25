"""Constants for the Multi Tariff Energy integration."""

DOMAIN = "multi_tariff_energy"

CONF_IMPORT_ENERGY_ENTITY = "import_energy_entity"
CONF_EXPORT_ENERGY_ENTITY = "export_energy_entity"
CONF_SOLAR_ENERGY_ENTITY = "solar_energy_entity"
CONF_STANDING_CHARGE = "standing_charge"
CONF_VAT_RATE = "vat_rate"
CONF_RATES_INCLUDE_VAT = "rates_include_vat"
CONF_VAT_ON_IMPORT = "vat_on_import"
CONF_VAT_ON_STANDING_CHARGE = "vat_on_standing_charge"
CONF_EXPORT_RATE = "export_rate"
CONF_CURRENCY = "currency"
CONF_BILLING_DAY = "billing_day"

DEFAULT_NAME = "Multi Tariff Energy"
DEFAULT_CURRENCY = "EUR"
DEFAULT_VAT_RATE = 0.0
DEFAULT_RATES_INCLUDE_VAT = False
DEFAULT_VAT_ON_IMPORT = True
DEFAULT_VAT_ON_STANDING_CHARGE = True
DEFAULT_STANDING_CHARGE = 0.0
DEFAULT_EXPORT_RATE = 0.0
DEFAULT_BILLING_DAY = 1

