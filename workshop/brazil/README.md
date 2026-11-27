<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Brazil (role 2): renewable supply in Rio Grande do Norte

Hand-over to role 1 (cable) and role 4 (economics). Status: second version,
weather year 2013. Region RN is agreed with role 1 (landing point Natal region,
see `workshop/cable/cable_route.py`).

Two scripts, both read only `data-brazil/` and write to `resources/brazil/`
(git-ignored):

| Script | Output | Use |
|---|---|---|
| `build_rn_potential.py` | potential per technology and class, hourly profiles | **input for the model** |
| `build_rn_onwind_profile.py` | one wind profile, state average | calibration and validation |

## Potential and profiles for the model

```bash
pixi run python workshop/brazil/build_rn_potential.py
```

About 45 seconds, under 2 GB of memory. Method as in PyPSA-Eur
(`determine_availability_matrix_MD_UA.py`, `build_renewable_profiles.py`):
eligible land from Copernicus LC100 with PyPSA-Eur's class mapping, protected
areas (WDPA) excluded, 1 km buffer around settlements for wind, capacity
densities from `config/config.default.yaml`.

`resources/brazil/rn_potential_2013.csv`:

| Carrier | Class | Eligible share of RN | Potential (GW) | CF unscaled | CF | Distance to converter (km) |
|---|---|---|---|---|---|---|
| onwind | 0 | 0.41 | 65 | 0.217 | 0.258 | 204 |
| onwind | 1 | 0.31 | 48 | 0.346 | 0.410 | 148 |
| onwind | 2 | 0.09 | 14 | 0.491 | 0.576 | 120 |
| solar-hsat | 0 | 0.87 | 204 | 0.238 | 0.238 | 179 |

Distance to converter: layout-weighted straight-line distance from the class
to the cable converter at Natal (the landing point in
`workshop/cable/add_brazil_cable.py`), like `average_distance` in PyPSA-Eur.

`resources/brazil/rn_profiles_2013_utc.csv`: index `timestamp_utc` (as below),
one column per row of the table (`onwind class 0` … `onwind class 2`,
`solar-hsat`), capacity factor per unit, 8760 hours.

- **Onshore wind:** Vestas V112 3 MW, 3 MW/km², 3 classes of equal capacity
  factor width as in the workshop baseline. Every class is scaled by the same
  factor to the ONS-measured RN wind farms (see below). The factor comes from
  the state average; for the best class it is an extrapolation, so its 0.576
  is rather an upper value.
- **Solar:** single-axis tracking (horizontal north-south axis), crystalline
  silicon, 4.43 MW/km² as PyPSA-Eur's `solar-hsat`, one class (eligible cells
  range from 0.217 to 0.257 only). Not scaled: there was no measured solar
  generation in RN in 2013. Matches the cost entry
  `solar-utility single-axis tracking`.
- **Wind and solar compete for the same land.** Their potentials must not be
  added; a shared land constraint is needed if both are built at scale.
- Potential is not the bottleneck: the cable is far smaller than either.

## In the model

`add_brazil_supply.py` is called from `scripts/compose_network.py` before the
cable. Off by default; a scenario turns it on together with the cable:

```yaml
brazil_cable:
  enable: true
brazil_supply:
  enable: true
  # start_year: 2040        # default: the cable's build year
  # carriers: [onwind, solar-hsat]
  # connection_cost: true
  # costs: brazil           # brazil (EPE, default) | europe (cost data)
  # cost_level: central     # low | central | high, EPE's range
```

Run `build_rn_potential.py` once first (the inputs are git-ignored, and
Snakemake does not track them: after rebuilding them add
`--forcerun compose_network`).

- Bus `Brazil Natal` (`carrier: AC`, `country: BR`) in every horizon.
- From the start year: one extendable generator per row of the potential table,
  carriers `Brazil onwind` and `Brazil solar-hsat`, names like
  `Brazil Natal onwind 2-2040`. Earlier builds are carried over by the
  brownfield step and subtracted from the potential.
- Profiles averaged to the model's snapshots as PyPSA-Eur does it.
- Capital cost: Brazilian costs (below) plus the onshore connection above,
  annualised as `scripts/process_cost_data.py` does (lifetime and discount
  rate of the cost data: 7 % in the main runs).
- No Brazilian demand, storage or grid: what the cable cannot take is
  curtailed.

Test runs with the cable at central level (`run: brazil-test`). With the
European cost data, 2025–2050: all horizons solve; 2045 ends "imprecise", like
the baseline's 2050.

| | 2040 | 2045 | 2050 |
|---|---|---|---|
| Brazil onwind built (GW, cumulative) | 5.1 | 5.1 | 5.3 |
| Brazil solar-hsat built (GW, cumulative) | 2.0 | 2.1 | 2.5 |
| Delivered to Germany (TWh) | 21.2 | 15.8 | 16.9 |
| Total system cost, baseline / with cable (bn EUR/a) | 64.5 / 75.5 | 74.1 / 84.6 | 93.3 / 103.6 |

With the Brazilian costs (EPE, central), 2040 only: 6.2 GW wind (best class)
and 1.3 GW solar, 22.1 TWh delivered, system cost 75.3 bn EUR/a. The cable's
annualised cost (about 12 bn EUR/a at central level) is far larger than what
it saves; cheaper Brazilian generation changes that little. A first check,
not the study result (role 4).

## Brazilian costs

`costs_brazil.yaml` (public values, with source and conversion), applied by
`add_brazil_supply.py` at runtime.

**Source:** EPE, *Power Generation Costs Report* (Caderno de Preços da
Geração), 2021, Table 13: CAPEX and O&M ranges from projects qualified for the
Brazilian regulated auctions 2010–2020, in BRL of December 2020. CAPEX includes
the grid connection and excludes interest during construction.

**Conversion to the agreed basis (role 4):**

1. IPCA (Banco Central do Brasil, series 433) from December 2020 to the 2025
   mean: × 1.3130.
2. ECB reference rate, annual mean 2025: 6.3072 BRL/EUR.
3. Grid connection removed (about 10 % of CAPEX for both technologies, EPE
   Figs. 7 and 18), so the definition matches the cost data; the onshore
   connection to Natal is added separately.
4. Later horizons: the 2025 value follows the relative change of the same
   technology in the cost data (`onwind`, `solar-utility single-axis
   tracking`).
5. O&M (fixed and variable together, BRL/kW/a) as FOM in % of the central
   plant investment; no separate VOM.

| | Unit | low | central | high | Cost data (Europe) |
|---|---|---|---|---|---|
| Onshore wind, 2025 | EUR/kW | 712 | 871 | 1,030 | 1,439 |
| Onshore wind, 2040 | EUR/kW | 646 | 791 | 935 | 1,306 |
| Onshore wind FOM | %/a | 2.15 | 2.15 | 2.15 | 1.19 |
| Solar, tracking, 2025 | EUR/kW | 525 | 684 | 843 | 695 |
| Solar, tracking, 2040 | EUR/kW | 365 | 476 | 587 | 483 |
| Solar FOM | %/a | 1.52 | 1.52 | 1.52 | 2.45 |

`central` is the midpoint of EPE's range, `low` and `high` its ends. Set
`costs: europe` for role 4's comparison case (the cost data unchanged).

Limitations:

- **One source, 2020 prices.** Wind turbine prices rose after 2020; EPE's
  newer studies (PDE) may give higher values and should be checked.
- **EPE does not separate fixed and tracking PV.** The range is applied to
  tracking PV, which is the common design in north-east Brazil, but it may
  include fixed-tilt plants (slightly cheaper).
- **PV per AC capacity.** EPE gives BRL per kW of inverter (AC) capacity; the
  cost data and the profiles are per kW as well, but the DC/AC ratio is not
  stated.
- **Learning from European data.** The decline to 2050 is taken from the cost
  data, not from a Brazilian projection.
- Wind CAPEX in Brazil is about 40 % below the European cost data at the
  nominal exchange rate. EPE notes that at purchasing power parity Brazilian
  costs are within the international range; role 4 runs PPP as a sensitivity.

## Single wind profile (calibration)

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
- **State average, not a site.** This single profile averages the whole state;
  the classes in `build_rn_potential.py` resolve the better sites.
- **No costs yet.** CAPEX, FOM and VOM for Brazil follow, on the same cost
  basis as Europe (cost year, currency, discount rate), agreed with role 4.
- **Solar not validated.** ERA5 (Europe uses SARAH-3, which does not cover
  western Brazil), no measured RN solar generation for 2013. PyPSA-Eur's default
  orientation (south, 35°) is wrong in the southern hemisphere and would cost
  about 17 % of the yield of fixed panels.
- **Wind and solar together.** Hourly correlation of the two profiles is about
  -0.1. ERA5 puts the wind maximum at night, which would complement solar; the
  measured maximum is in the late afternoon, so the complementarity is weaker
  than the profiles suggest.

## For role 1 (cable)

### Answers to your requests 1–3 (`workshop/cable/README.md`)

Please copy these into your table and set them to agreed.

| # | Answer |
|---|---|
| 1 | **Agreed: bus `Brazil Natal`** (`carrier: AC`, `country: BR`), at your Natal coordinates. Role 2 creates it and attaches the RN supply; keep `bus_brazil` at its default. |
| 2 | **Agreed:** role 2's call goes into `scripts/compose_network.py` **before** your cable call, in its own file under `workshop/brazil/`, same pattern as yours (off by default). |
| 3 | **Role 2 takes the onshore connection** from the generators to the converter at Natal. Your cable cost stays sea route plus converters. |

### Onshore connection (role 2)

Method as PyPSA-Eur does it for offshore wind (`attach_wind_and_solar` in
`scripts/add_electricity.py`): connection cost = distance × length factor ×
line cost, added to the generator's capital cost.

| Class | Distance (km) | Connection, 2040 (EUR/MW) | Share of plant investment, cost data / Brazil (EPE central) |
|---|---|---|---|
| onwind 0 | 204 | about 173,000 | about 13 % / 22 % |
| onwind 1 | 148 | about 126,000 | about 10 % / 16 % |
| onwind 2 | 120 | about 102,000 | about 8 % / 13 % |
| solar-hsat | 179 | about 152,000 | about 32 % / 32 % |

Values from `data/costs/archive/v0.15.0/costs_2040.csv` (EUR 2025):
`HVAC overhead` 680 EUR/MW/km (European line cost; no Brazilian line cost is
used), length factor 1.25 (`lines.length_factor` in
`config/config.default.yaml`). Plant investment: the cost data and the
Brazilian costs below.

- The distances are straight lines to one point. They do not include the
  collector grid inside a wind or solar farm, nor a substation.
- The share for solar is high because solar is cheap per MW and the eligible
  land is spread over the whole state. Closer sites would lower it; the
  potential (204 GW) is far larger than the cable, so the model could be
  limited to sites near Natal.
- The coast distance of about 73 km given in the first version of this README
  is not used: it was the median distance of all RN cells to the sea, not a
  connection length.

## For role 4 (economics)

- Carry the wind capacity factors with and without scaling as a range (column
  `cf_unscaled` in the potential table). The difference of about 18 % feeds
  directly into the cost per MWh.
- The scaling factor belongs in the sensitivity analysis.

### Cost basis, agreed with role 4

Role 4 answered in `workshop/economics/STUDY_DESIGN.md` ("Answers to role 2's
questions"). Role 2 adopts answers 1–5; on answer 6 role 2 keeps its own
carriers (see below).

| # | Point | Agreed |
|---|---|---|
| 1 | Price base | EUR 2025. Older BRL sources are inflated to 2025 with IPCA, then converted. |
| 2 | BRL to EUR | ECB reference rate, annual mean 2025, one fixed rate; rate and source stated next to the costs. Purchasing power parity only as a sensitivity. |
| 3 | Cost of capital | Role 2 delivers no rate: investment, FOM, VOM and lifetime only. Main runs 7 %; the project-finance runs get a Brazilian rate from role 4 at runtime. |
| 4 | Lifetimes | As in the cost data: onshore wind 30 years, utility PV 40 years. |
| 5 | Source | Main case: Brazilian sources (e.g. EPE, IRENA) in EUR 2025; comparison: the European cost data unchanged. Same definition as the cost data: overnight investment without grid connection beyond the plant (the onshore connection is added separately, above). |
| 6 | Commissioning, naming | From the cable's build year, bus `Brazil Natal`, `Brazil` in every name: agreed. **Carrier: role 2 keeps `Brazil onwind` and `Brazil solar-hsat`** (not the plain technology). |

Why own carriers: constraints written per carrier for Germany would otherwise
include the Brazilian plants without anyone noticing, e.g. role 3's capacity
path (`config/workshop/wind-path.yaml`, carrier `onwind`) and the solar land
constraint in `scripts/solve_network.py` (`solar`, `solar-hsat`).

**Request to role 4 (plot style, evaluation):** `workshop/plotstyle/studystyle.py`
maps every carrier containing "Brazil" to the cable group. Please map only
`Brazil cable` there and `Brazil onwind` / `Brazil solar-hsat` to their
technology groups (or to a Brazil group), and tell Brazilian plants by the
bus country in `analyse_runs.py` as planned.

The Brazilian costs (case 5b, EPE) are in; the European cost data stay
available as the comparison (`costs: europe`). See "Brazilian costs" above.

## Sources

ERA5 (CC-BY-4.0), ONS Dados Abertos (CC-BY-4.0), Copernicus LC100 (free with
attribution), WDPA (non-commercial use), GADM 4.1 state borders. WDPA and GADM
are only read from `data-brazil/` and not redistributed. Costs: EPE Power
Generation Costs Report 2021 (CC-BY-4.0, EPE website), IPCA from Banco Central
do Brasil (SGS 433), ECB reference exchange rates; all retrieved 2026-11-27.
