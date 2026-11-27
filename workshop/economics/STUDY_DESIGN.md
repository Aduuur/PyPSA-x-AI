<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Study design (role 4, draft)

What the group compares, with which parameters, and how runs are named and
evaluated. Status: **draft**, open points marked _to agree_.

## The question

What is a Brazil–Germany HVDC cable worth to the German power system from
2035 on, to whom, and under which conditions does that hold?

## Design

- **Main result: cost-benefit analysis of a given cable.** Two runs that differ
  in one thing only: the baseline (`de10-myopic`) and the same model with the
  cable (capacity, cost and Brazilian supply from roles 1 and 2). The value of
  the cable is the difference in system cost, plus who gains and who loses.
- **Second step (optional): capacity expansion.** The model chooses the cable
  size; shows how large the cable should be at its cost.
- **Horizons:** the baseline's 2025–2050 in 5-year steps, myopic. The cable is
  available from its commissioning year (_to agree with role 1_, earliest 2035).
- **2050:** the zero CO2 cap prices CO2 at about 24,000 EUR/t in 2050, so any
  clean power looks extremely valuable that year. The headline result is the
  present value over **2035–2045**; 2050 is shown separately, plus a
  sensitivity with a relaxed 2050 cap, with and without the cable
  (`cap2050-relaxed`, level _to agree with role 3_).

## Harmonised economic parameters

One set for Germany, Brazil and the cable. Every role uses it.

| Parameter | Value | Where |
|---|---|---|
| Currency and price base | EUR, price base of the cost data | `costs` |
| Annuities (investment) | 7% unless set per asset | `costs.fill_values` / cost data |
| Social discount rate (present value across horizons) | 2% | `costs.social_discountrate` |
| Present value base year | 2025 | evaluation |
| Each horizon stands for | the 5 years up to the next one | evaluation |
| BRL to EUR | one fixed rate for all Brazilian costs | _to agree with role 2_ |
| Lifetimes cable, converters, Brazilian plants | | _to agree with roles 1, 2_ |

Asset-specific costs of capital that come from confidential documents are
**not** written into any shared config. A script reads them at runtime and
writes a config layer to `workshop/private/` (git-ignored); see "Confidential
data" in `AGENTS.md`. Only whole-model results are shared.

## Scenarios

Each scenario is a config file in `config/workshop/`, layered on the workshop
config, with its own `run: name`. Two runs that are compared differ in one
thing only.

| Run | Differs from | in | Status |
|---|---|---|---|
| `de10-myopic` | – | baseline | solved |
| `cable` | `de10-myopic` | the cable | waits for roles 1, 2 |
| `cable-cost-high`, `cable-cost-low` | `cable` | cable cost | waits for role 1 |
| `cable-wacc` | `cable` | cost of capital | waits for role 4 input |
| `cap2050-relaxed` | `de10-myopic` | 2050 cap | config ready |
| `cable-cap2050-relaxed` | `cable` | 2050 cap | waits for `cable` |

A full run takes about 20 minutes, so keep the list short.

## How to run a scenario

No run may overwrite another. A run with its own name needs its own
`resources/<run>/`; link the pre-built inputs instead of rebuilding them:

```bash
sh workshop/economics/link_inputs.sh <run>
pixi run snakemake results/<run>/networks/solved_2050.nc -c4 \
  --configfile config/config.workshop.yaml config/workshop/<run>.yaml \
  --allowed-rules process_cost_data compose_network solve_network
```

This works for everything changed at or after network composition (costs,
CO2, demand, new components). Changing clustering, weather year or time
resolution needs a full rebuild (`workshop/BASELINE.md`).

## Evaluation

`workshop/economics/analyse_runs.py` reads every solved run and writes tables
and figures to `results/economics/`:

```bash
pixi run python workshop/economics/analyse_runs.py --reference de10-myopic
```

Per run and horizon: system cost by technology group, demand, load-weighted
and peak price, emissions, price of the CO2 cap, generation and capacity, flow
and rent of the Brazil cable, consumer cost, producer surplus by group,
congestion rent. Present values for all horizons and for 2035–2045. Every run
is compared with the reference.

## What the other roles deliver

- **Role 1:** the cable as a link whose name contains `Brazil` (the evaluation
  and the plot style recognise it by that), its capacity, cost and
  commissioning year, all in EUR at the price base above.
- **Role 2:** Brazilian supply as components whose names contain `Brazil`,
  costs in EUR at the agreed rate.
- **Role 3:** the decision on 2050 and whether the German model is good enough
  to judge the cable; how long a run takes.
