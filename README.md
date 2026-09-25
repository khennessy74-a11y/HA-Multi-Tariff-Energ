# HA-Multi-Tariff-Energ

Home Assistant custom integration for tracking electricity costs across multiple time-of-use tariffs using existing cumulative energy sensors.

## Features

- Multiple named import tariffs, including multiple time windows for the same tariff name.
- Grid import and export accounting, with optional solar production tracking.
- Daily, monthly and billing-cycle energy and cost totals.
- Yesterday, last month and previous billing-cycle totals.
- Standing charge and configurable VAT handling.
- Export credit and net electricity cost.
- Current tariff/rate plus the next tariff, rate and change time.
- Per-tariff import energy and cost sensors.
- Persistent accounting across Home Assistant restarts.
- Safe handling of cumulative meter resets and configured source changes.
- Exact Decimal accounting and Wh, kWh, MWh and GWh source normalization.

## Requirements

Choose cumulative Home Assistant sensors with the `energy` device class for grid import and grid export. Solar production is optional.

Source readings are normalized to kWh before accounting. A source without a unit is treated as kWh for backwards compatibility. Unsupported units are ignored rather than charged incorrectly.

## Tariff schedules

The import tariff schedule must cover the complete 24-hour day without gaps or overlaps. A tariff name may be reused in separate windows, and those windows are combined into the same tariff totals.

For example:

| Tariff | Start | End |
| --- | --- | --- |
| Night | 23:00 | 08:00 |
| Day | 08:00 | 17:00 |
| Peak | 17:00 | 19:00 |
| Day | 19:00 | 23:00 |

The two Day windows are reported together.

## Cost accounting

The integration accounts only for positive changes in the cumulative source meters; it never multiplies the full cumulative meter value by the current tariff.

Import energy is charged using the tariff active when the delta is processed. Export energy receives the configured export rate. The daily standing charge is applied once per local calendar day.

Net cost is:

`import energy charges + standing charge + VAT added - export credit`

If tariff rates already include VAT, the VAT component is reported but is not added to the net cost a second time. VAT can independently be enabled for imported electricity and the standing charge.

## Billing cycles

Set the billing day from 1 to 28. The integration tracks the current and immediately previous billing cycle independently of calendar-month totals.

## Configuration changes

Source sensors, billing settings and tariff schedules can be changed from the integration's Configure screen. Existing tariff windows are preserved unless **Replace tariff schedule** is enabled.

Before applying configuration changes, current source readings are snapshotted using the old configuration. This prevents unprocessed consumption from being moved onto a newly configured tariff or rate.

## Important limitation

Tariff boundaries are scheduled in Home Assistant local time. At a tariff boundary the integration snapshots the latest source reading and assigns the accumulated delta to the tariff that has just ended.

If the underlying cumulative source sensor has not published a fresh reading at the exact boundary, the integration cannot reconstruct exactly how consumption since its previous update was split across that boundary. Recorder/history-based reconstruction is not currently implemented.

## Installation

This repository is under active development. Until a release package is published, install it manually by copying `custom_components/multi_tariff_energy` into the `custom_components` directory of your Home Assistant configuration and restart Home Assistant.

Then go to **Settings → Devices & services → Add integration** and search for **Multi Tariff Energy**.

## Support the project

If you find this integration useful and would like to support its continued development, you can [Buy Me a Coffee](https://buymeacoffee.com/khennessy74).

Support is completely optional and does not affect access to any features.
