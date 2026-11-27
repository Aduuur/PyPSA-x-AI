<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Brazil (role 2): onshore wind profile for Rio Grande do Norte

Hand-over to role 1 (cable) and role 4 (economics). Status: first version,
weather year 2013. Region RN is agreed with role 1 (landing point Natal region,
see `workshop/cable/cable_route.py`).

## Build the profile

The profile is not committed as data: build it in your workspace from
`data-brazil/` (about 10 seconds, under 1 GB of memory):

```bash
pixi run python workshop/brazil/build_rn_onwind_profile.py
```

It writes `resources/brazil/rn_onwind_cf_2013_utc.csv` (git-ignored):

| Column | Meaning |
|---|---|
| `timestamp_utc` | hour start, ISO 8601, UTC (no daylight saving), `2013-01-01T00:00:00Z` to `2013-12-31T23:00:00Z` |
| `rn_onwind_cf` | onshore wind capacity factor, per unit (0 to 1), 4 decimals |

8760 rows, no gaps. Same time axis as the model snapshots (weather year 2013, UTC).

```python
import pandas as pd
cf = pd.read_csv("resources/brazil/rn_onwind_cf_2013_utc.csv",
                 index_col="timestamp_utc", parse_dates=True)["rn_onwind_cf"]
cf.index = cf.index.tz_localize(None)  # model snapshots are naive UTC
```

## How it is made

1. Hourly capacity factor per ERA5 grid cell from the Brazil cutout
   (`data-brazil/weather/brazil-2013-era5.nc`, atlite 0.6.1, turbine
   `Vestas_V112_3MW`), averaged over the 47 cells whose centre lies inside the
   state of RN. No land eligibility applied: it is the average over the whole
   state.
2. Scaled to the measured level, clipped at 1 per cell and hour (2.5 % of
   cell-hours affected).

The scaling factor (1.19) is computed by the script: capacity factor of the RN
wind farms measured by ONS (`GERACAO_USINA-2_2013.parquet`, hourly
generation; capacity from `CAPACIDADE_GERACAO.csv`, units in operation on
2013-12-31) divided by the unscaled ERA5 capacity factor over the same hours.
Only farms that report the whole year and have register capacity are used:
6 farms, 256 MW. ONS times are converted from Brasília legal time to UTC as in
`data-brazil/README.md`, which also notes that ERA5 underestimates wind speeds
in north-east Brazil.

An earlier factor of 2, from comparing ERA5 with ONS wind generation for the
whole NE subsystem, is not used: the register lacks part of the 2013 fleet, so
the capacity behind it was too small.

## Key figures (2013)

| | Value |
|---|---|
| Mean CF, ERA5 unscaled | 0.297 |
| Mean CF, profile | 0.352 |
| Mean CF, 6 measured farms | 0.354 |
| Correlation with the measured farms: monthly / daily / hourly | 0.84 / 0.72 / 0.40 |
| Hour of the daily maximum (UTC): measured / profile | 19 h / 23 h |
| Full-load hours, profile / unscaled | about 3,080 / 2,600 h per year |

## Limitations

- **One weather year.** No information on year-to-year variation.
- **Hourly shape only partly reliable.** The daily maximum comes about 4 hours
  later than in the measured data. The time stamps are not the cause: the
  plant data use the same time stamps as the ONS energy balance, and both
  were converted to UTC. Shifting the profile by 4 hours would raise the
  hourly correlation to about 0.58; this is not done because the cause is
  unknown. Fine for annual energy and seasonality, not for questions that
  depend on single hours (cable congestion, storage).
- **Scaling factor from few farms.** 6 farms, one year, not spread over the
  whole coast. Not included: 3 farms that started feeding in during
  October/November 2013 (commissioning, register date 2014) and 1 farm that
  is missing from the register.
- **State average, not a site.** Real projects would be built on the better
  sites, with higher capacity factors.
- **No costs yet.** CAPEX, FOM and VOM for Brazil follow, on the same cost
  basis as Europe (cost year, currency, discount rate), agreed with role 4.
- **Wind only.** Solar is not done yet. Unscaled ERA5 solar capacity factors
  (fixed, latitude-optimal tilt) are 0.17 to 0.19 in all north-eastern states.

## For role 1 (cable)

- Median distance to the coast of the RN cells: about 73 km (coarse, from a
  GEBCO grid of about 0.17°; not a route).

## For role 4 (economics)

- Carry both mean values (0.352 scaled, 0.297 unscaled) as a range. The
  difference of about 18 % feeds directly into the cost per MWh.
- The scaling factor belongs in the sensitivity analysis.

## Sources

ERA5 (CC-BY-4.0), ONS Dados Abertos (CC-BY-4.0), GADM 4.1 state borders (used
only to select the grid cells; not redistributed).
