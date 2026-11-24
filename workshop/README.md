<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Workshop baseline: Germany in Europe, 2025–2050

This branch holds the baseline every group starts from: the power sector of
Europe with Germany split into 4 nodes and one node per country elsewhere,
solved with myopic foresight from 2025 to 2050 in 5-year steps. The settings are
in [`config/config.workshop.yaml`](../config/config.workshop.yaml) (run name
`de4-myopic`); everything not set there keeps its value in
`config/config.default.yaml`.

Everything slow to build is pre-built, so you can start by composing and
solving networks instead of downloading 9 GB and rebuilding the network.

## Setup (about 10 minutes)

1. Clone this branch and install the environment:

   ```bash
   git clone --branch workshop-baseline https://github.com/lkslab/pypsa-eur.git
   cd pypsa-eur
   pixi install
   ```

2. Download `europe-de4-myopic-prebuilt-2026-11-24.tar.zst` (0.9 GB) and
   `europe-2026-11-24.sha256` from the Zenodo record into the repository root
   (ZENODO_LINK; the files open with the share link you got from the
   organisers), check and unpack it:

   ```bash
   sha256sum -c europe-2026-11-24.sha256 --ignore-missing
   tar --zstd -xf europe-de4-myopic-prebuilt-2026-11-24.tar.zst
   ```

   This fills `resources/de4-myopic/` (clustered network, wind, solar and hydro
   profiles, demand, power plants, processed costs), `results/de4-myopic/networks/`
   (the six solved baseline networks) and the few downloaded files the model
   step reads (`data/costs/`, `data/ghg_emissions/`).

3. Tell Snakemake the unpacked files are up to date. Your checkout is newer than
   the bundle, so without this step it would redo all the work:

   ```bash
   pixi run snakemake results/de4-myopic/networks/solved_2050.nc -c4 --touch \
     --configfile config/config.workshop.yaml \
     --allowed-rules process_cost_data compose_network solve_network
   ```

## Running the model

Use the same command without `--touch`. Put the target first: `--configfile`
and `--allowed-rules` take several values and would swallow it.

```bash
pixi run snakemake results/de4-myopic/networks/solved_2050.nc -c4 \
  --configfile config/config.workshop.yaml my-changes.yaml \
  --allowed-rules process_cost_data compose_network solve_network
```

`--allowed-rules` keeps Snakemake from rebuilding the pre-built inputs; only
the cost processing, the network composition and the solves run. Changes to the
config are picked up and rerun the horizons they affect. All six horizons take
about 45 minutes with Gurobi and 8 threads; each solve needs up to 12 GB of
memory. Add `--forcerun compose_network` after changing model code that
Snakemake does not track as an input.

The solved networks in the bundle are what this config produces, so you can
also open them right away:

```python
import pypsa
n = pypsa.Network("results/de4-myopic/networks/solved_2030.nc")
```

### Solver

The config uses Gurobi (free academic licences at gurobi.com). Without it, set
`solving: {solver: {name: highs, options: highs-default}}` in your own config
file; expect each horizon to take much longer.

## When you need the raw data

The pre-built bundle covers changes made at or after network composition:
demand, costs, CO₂ prices and caps, grid limits, lifetimes, new components and
constraints. Changing the clustering (for example more German nodes), the
weather year or the renewable settings rebuilds the network and profiles from
raw data. For that, also download `europe-raw-data-2026-11-24.tar.zst`
(8 GB, including the 2013 ERA5/SARAH-3 weather cutout) and unpack it in the
repository root, then run Snakemake without `--allowed-rules`. Building from it
takes about 20 minutes plus the solves.

## Brazil data

The same Zenodo record holds `brazil-workshop-data.zip` (6.3 GB) with the inputs
for the Brazil side, for weather year 2013:
- an ERA5 weather cutout;
- land cover, protected areas, elevation, ship density and the exclusive economic
  zone, cut to Brazil;
- Atlantic bathymetry for the cable route;
- grid operator (ONS) load, inflow, generation and interchange data;
- power plant and state-level data.

Nothing in it is a model yet. Unpack it into `data/` (which git ignores) and
start with its `README.md`, which maps every file and the traps in the data:

```bash
sha256sum -c brazil-workshop-data.zip.sha256
unzip brazil-workshop-data.zip -d data/
```

Some of its sources (GADM, WDPA) must not be redistributed, so keep the zip
within the workshop.

## What the baseline assumes

| Setting | Value | Where |
|---|---|---|
| Scope | power only, 34 countries, weather year 2013, 3-hour resolution | `sector.enabled: false`, `clustering.temporal` |
| Nodes | 43: Germany 4, one per country and synchronous zone elsewhere | `clustering` |
| 2025 | today's fleet and grid, dispatch only | `existing_capacities.freeze_first_horizon` |
| Plant retirement | recorded closure date, else lifetime from last retrofit; nuclear 60 years, gas 35 | `costs.overwrites` |
| Demand | today's hourly shape, scaled 1.0 to 1.5 by 2050 (TYNDP 2024 Distributed Energy, without electrolysis) | `load.scaling_factor` |
| CO₂ | price 80 €/t in 2025 rising to 300 €/t in 2050, plus a cap falling to zero in 2050 | `costs.emission_prices`, `co2_budget` |
| Grid | total line volume may grow 25% over today; cross-border AC lines carry at most 30% of their rating | `electricity.transmission_limit`, `lines.s_max_pu_crossborder` |
| Wind and solar | three site-quality classes per node | `renewable.*.resource_classes` |

## Results at a glance (Germany)

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|---|---|
| Demand (TWh) | 509 | 560 | 611 | 662 | 713 | 764 |
| Net imports (TWh) | 11 | 117 | 115 | 108 | 93 | 120 |
| CO₂ from German plants (Mt) | 151 | 16 | 15 | 16 | 17 | 0 |
| Average price (€/MWh) | 100 | 72 | 85 | 86 | 91 | 112 |

## Known limitations

- Neighbouring countries are single nodes, so all their border circuits add up;
  the cross-border derating offsets this only roughly.
- Hard coal runs far ahead of lignite in 2025 because the cost data prices
  lignite fuel like hard coal.
- The zero CO₂ cap in 2050 is met only at an extreme shadow price (tens of
  thousands of €/t) with winter price peaks above 4,000 €/MWh.
- Myopic foresight: each horizon sees only its own year, so nothing is built
  for later needs.
