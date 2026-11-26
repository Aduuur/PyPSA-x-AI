<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Workshop baseline: Germany, 2025–2050

This branch holds the baseline every group starts from: the power sector of
Germany alone with 10 nodes, in 2-hour steps, solved with myopic foresight from
2025 to 2050 in 5-year steps. There are no neighbouring countries, so no imports
or exports. The settings are in
[`config/config.workshop.yaml`](../config/config.workshop.yaml) (run name
`de10-myopic`); everything not set there keeps its value in
`config/config.default.yaml`.

The model is sized for the workshop workspaces: one solve stays under 8 GB of
memory and takes a few minutes on 4 CPUs.

## In your workspace

Everything is ready in `~/pypsa-eur`: the environment, the network, the wind,
solar and hydro profiles, demand, power plants and the six solved baseline
networks. Open one right away:

```python
import pypsa
n = pypsa.Network("results/de10-myopic/networks/solved_2030.nc")
```

## Running the model

Put your changes in your own config file and list it after the workshop config.
Put the target first: `--configfile` and `--allowed-rules` take several values
and would swallow it.

```bash
pixi run snakemake results/de10-myopic/networks/solved_2050.nc -c4 \
  --configfile config/config.workshop.yaml my-changes.yaml \
  --allowed-rules process_cost_data compose_network solve_network
```

`--allowed-rules` keeps Snakemake from rebuilding the pre-built inputs; only
the cost processing, the network composition and the solves run. Changes to the
config are picked up and rerun the horizons they affect. All six horizons take
about 20 minutes. Add `--forcerun compose_network` after changing
model code that Snakemake does not track as an input.

To keep the baseline next to your own results, give your config a different
`run: {name: ...}`. That needs its own inputs, so see "Rebuilding the inputs".

### Memory

A workspace is stopped by the system when it runs out of memory, so the model
is kept small. Measured peak per solve, inside an 8 GB limit:

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|---|---|
| Peak memory (GB) | 4.1 | 6.1 | 6.1 | 6.1 | 6.8 | 6.5 |
| Solver time (min) | 0.5 | 3.0 | 2.3 | 2.1 | 3.2 | 3.7 |

Two steps in [`data/custom_extra_functionality.py`](../data/custom_extra_functionality.py)
run before every solve and keep it there. They do not change the problem that is
solved:

- The limits of plants with fixed capacity become bounds on the variables
  instead of constraints. This takes more than half of the rows out of the
  matrix. In return, the shadow prices of these limits (`mu_upper`, `mu_lower`
  of fixed-capacity components) are not reported.
- The file handed to the solver is written to `results/<run>/solver_tmp/`
  instead of `/tmp`, which on many Linux systems lives in memory.

Add your own constraints to that file below these two steps. More nodes, a
finer time resolution or many new components make the model bigger: 1-hour
steps would roughly double the memory.

If a solve is killed for lack of memory, Snakemake leaves a lock and marks the
output as incomplete. Clear both before the next run:

```bash
pixi run snakemake --unlock --configfile config/config.workshop.yaml
pixi run snakemake results/de10-myopic/networks/solved_2050.nc -c4 --rerun-incomplete \
  --configfile config/config.workshop.yaml my-changes.yaml \
  --allowed-rules process_cost_data compose_network solve_network
```

### Solver

The config uses COPT with the floating licence of PyPSA Labs. In a workspace it
is set up already. Elsewhere, put the `client.ini` you got from the organisers
into `~/copt/`. Without COPT, set
`solving: {solver: {name: highs, options: highs-default}}` in your own config
file; expect each horizon to take much longer.

In your own Python scripts, import `pypsa` before `coptpy`; the other order
crashes the interpreter.

## Rebuilding the inputs

Changes made at or after network composition need no rebuild: demand, costs,
CO₂ prices and caps, grid limits, lifetimes, new components and constraints.
Changing the clustering (for example more nodes), the weather year, the
renewable settings or the time resolution rebuilds inputs from the raw data.
In a workspace the raw data is linked into `data/`. Run Snakemake without
`--allowed-rules`:

```bash
pixi run snakemake results/de10-myopic/networks/solved_2050.nc -c4 \
  --configfile config/config.workshop.yaml my-changes.yaml
```

Building everything from the raw data takes about 7 minutes
plus the solves. The wind and solar profile jobs need 3 to 4 GB each, so the
branch's Snakemake profile runs them one at a time.

## Outside a workspace

```bash
git clone --branch workshop-baseline https://github.com/lkslab/pypsa-eur.git
cd pypsa-eur
pixi install --frozen
pixi run --frozen snakemake results/de10-myopic/networks/solved_2050.nc -c4 \
  --configfile config/config.workshop.yaml
```

The lock file needs pixi 0.84 or newer; with an older pixi, keep `--frozen` on
every `pixi run`. There is no pre-built bundle for this baseline. Without the
raw data in `data/`, the workflow's own retrieve rules download it (several GB,
weather data included); that path was not tested for the workshop.

## Brazil data

The Zenodo record <https://zenodo.org/records/24503133> holds
`brazil-workshop-data.zip` (6.3 GB) with the inputs for the Brazil side, for
weather year 2013. The files open with the share link you got from the
organisers; in a workspace they are already under `data-brazil/`.
- an ERA5 weather cutout;
- land cover, protected areas, elevation, ship density and the exclusive economic
  zone, cut to Brazil;
- Atlantic bathymetry for the cable route;
- grid operator (ONS) load, inflow, generation and interchange data;
- power plant and state-level data.

Nothing in it is a model yet. Start with its `README.md`, which maps every file
and the traps in the data. Outside a workspace, unpack it into `data/` (which
git ignores):

```bash
sha256sum -c brazil-workshop-data.zip.sha256
unzip brazil-workshop-data.zip -d data/
```

Some of its sources (GADM, WDPA) must not be redistributed, so keep the zip
within the workshop.

## What the baseline assumes

| Setting | Value | Where |
|---|---|---|
| Scope | power only, Germany alone, weather year 2013, 2-hour resolution | `countries`, `sector.enabled: false`, `clustering.temporal` |
| Nodes | 10 | `clustering.cluster_network` |
| Trade | none: no neighbours, no imports or exports | `countries` |
| 2025 | today's fleet and grid, dispatch only | `existing_capacities.freeze_first_horizon` |
| Plant retirement | recorded closure date, else lifetime from last retrofit; nuclear 60 years, gas 35 | `costs.overwrites` |
| Demand | today's hourly shape, scaled 1.0 to 1.5 by 2050 (TYNDP 2024 Distributed Energy, without electrolysis) | `load.scaling_factor` |
| CO₂ | price 80 €/t in 2025 rising to 300 €/t in 2050, plus a cap falling to zero in 2050 | `costs.emission_prices`, `co2_budget` |
| Grid | total line volume may grow 25% over today | `electricity.transmission_limit` |
| Wind and solar | three site-quality classes per node | `renewable.*.resource_classes` |

## Results at a glance

| | 2025 | 2030 | 2035 | 2040 | 2045 | 2050 |
|---|---|---|---|---|---|---|
| Demand (TWh) | 509 | 560 | 611 | 662 | 713 | 764 |
| Wind (TWh) | 146 | 214 | 246 | 255 | 339 | 422 |
| Solar (TWh) | 86 | 142 | 189 | 273 | 337 | 432 |
| Gas (TWh) | 21 | 108 | 114 | 93 | 47 | 0 |
| Hard coal and lignite (TWh) | 163 | 27 | 1 | 0 | 0 | 0 |
| CO₂ (Mt) | 161 | 64 | 43 | 34 | 17 | 0 |
| Average price (€/MWh) | 96 | 87 | 91 | 93 | 113 | 117 |
| Battery storage (GWh) | 0 | 20 | 155 | 391 | 607 | 834 |
| Hydrogen storage (TWh) | 0 | 0 | 0 | 0 | 13 | 72 |

## Known limitations

- Germany is an island: no imports, exports or transit. Scarcity that trade
  would cover shows up as storage, backup capacity and high prices.
- Hard coal runs far ahead of lignite in 2025 because the cost data prices
  lignite fuel like hard coal.
- The zero CO₂ cap in 2050 is met with large hydrogen storage and price peaks
  in the thousands of €/MWh.
- Myopic foresight: each horizon sees only its own year, so nothing is built
  for later needs.
- A horizon can end with the solver status "imprecise" (2050 in the reference
  run): the barrier stopped just short of its tolerance, with a relative gap of
  2e-7. The results are usable.
