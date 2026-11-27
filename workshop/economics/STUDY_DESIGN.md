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
| Currency and price base | **EUR 2025** (see answer 1 below) | all roles |
| Annuities (investment) | 7% (harmonised); asset rates only in the project-finance runs | `costs.fill_values` / `financing.py` |
| Social discount rate (present value across horizons) | 2% | `costs.social_discountrate` |
| Present value base year | 2025 | evaluation |
| Each horizon stands for | the 5 years up to the next one | evaluation |
| BRL to EUR | ECB reference rate, annual mean 2025, one fixed rate | agreed with role 2 |
| Lifetimes | as in the cost data (onshore wind 30, utility PV 40 years); cable from role 1 | agreed with roles 1, 2 |

### Answers to role 2's questions (`workshop/brazil/README.md`)

1. **Price base: EUR 2025.** In the cost data the model uses
   (`data/costs/archive/v0.15.0`), the investment of every technology that
   matters for this study (`onwind`, `solar-utility single-axis tracking`,
   `HVDC submarine`, `HVDC inverter pair`) has `currency_year` 2025 in every
   horizon. The model does not convert between currency years, so EUR 2025 is
   the common base. FOM is a percentage of the investment, so its own currency
   year does not matter. Brazilian costs are converted to EUR 2025: first
   inflate BRL to 2025 with the Brazilian price index (IPCA) where a source is
   older, then convert at the rate in answer 2. Role 1 is already on this base.
2. **BRL to EUR: agreed.** ECB reference rate, annual mean 2025, one fixed rate
   for all Brazilian costs. State the rate and its source next to the costs.
   Purchasing power parity only as a sensitivity, not in the main case. (The
   rate in the financing term sheet is confidential and is not used for this.)
3. **Cost of capital: role 2 delivers no rate.** Investment, FOM, VOM and
   lifetime only. The main runs use the harmonised 7% for Brazil as for
   Germany. The project-finance runs use an own rate for Brazilian generation
   (country risk), set by role 4 at runtime through the private layer in
   `workshop/private/`; role 2 does not touch it.
4. **Lifetimes: agreed.** As in the cost data (onshore wind 30, utility PV
   40 years), Brazil and Germany alike.
5. **Source: agreed.** (b) Brazilian sources (e.g. EPE, IRENA) converted to
   EUR 2025 as the main case, (a) the European cost data unchanged as the
   comparison. Same definition as the cost data: overnight investment without
   interest during construction and without grid connection beyond the plant,
   FOM in % of investment per year, VOM in EUR/MWh. A cost advantage of Brazil
   must come from the sources, not from a different definition.
6. **Commissioning and naming: agreed.** Brazilian generators are available
   from the cable's build year (role 1: 2040 central, 2035–2045 as range),
   attached to the bus `Brazil Natal` (role 1's proposal, `country: BR`),
   with `Brazil` in every component name (e.g. `Brazil onwind class 2`). The
   carrier stays the plain technology (`onwind`, `solar-hsat`), not
   `Brazil ...`: the plot style maps every carrier containing "Brazil" to the
   cable's colour. The evaluation will tell Brazilian from German plants by
   the bus country (to be added to `analyse_runs.py` by role 4).

Asset-specific costs of capital that come from confidential documents are
**not** written into any shared config. A script reads them at runtime and
writes a config layer to `workshop/private/` (git-ignored); see "Confidential
data" in `AGENTS.md`. Only whole-model results are shared.

### Cost of capital per asset (`workshop/economics/financing.py`)

Three assets: German grid connection and onshore works (`germany`), Brazilian
generation (`brazil`), subsea cable and converter stations (`cable`). For each,
the module derives at runtime from the financing term sheet:

- `wacc`: after-tax WACC, used for the annuity instead of the default 7%;
- `idc_factor`: interest during construction, multiplies the overnight
  investment before the annuity is applied;
- for Brazil: the BRL/EUR rate for converting Brazilian costs.

Roles 1 and 2 use it in `compose_network` when they add their components,
never with values typed in:

```python
sys.path.insert(0, "workshop/economics")
from financing import load, annuity
fin = load()["cable"]
capital_cost = investment * fin["idc_factor"] * (annuity(fin["wacc"], lifetime) + fom_share)  # FOM as a fraction
```

If the term sheet is not in a workspace, `load()` fails loudly; it does not
fall back to a default. `pixi run python workshop/economics/financing.py`
checks the figures for plausibility and writes `workshop/private/financing.yaml`
without printing them.

Comparison: the `cable` run uses the harmonised 7%; `cable-project` uses the
asset rates and IDC, so the effect of project finance is visible on its own.

## Scenarios

Each scenario is a config file in `config/workshop/`, layered on the workshop
config, with its own `run: name`. Two runs that are compared differ in one
thing only.

**Reference: Germany with border trade (`de10-trade`).** Against the island
baseline, any new source of power is worth too much: the island has no other
way to import in a scarcity hour. The main runs therefore all carry role 3's
border trade (`config/workshop/border-trade.yaml`), and the cable is judged
against `de10-trade`. The island runs stay as a comparison that shows how much
of the cable's value comes from Germany having no neighbours.

Main runs, each layered on the workshop config and `border-trade.yaml`:

| Run | Differs from | in | Status |
|---|---|---|---|
| `de10-trade` | `de10-myopic` | border trade (role 3) | solving |
| `trade-cable` | `de10-trade` | the cable (role 1 central) | config ready, waits for the Brazilian supply (role 2) |
| `trade-cable-cost-low`, `trade-cable-cost-high` | `trade-cable` | role 1 low / high level | config ready, waits as above |
| `trade-cap2050-relaxed` | `de10-trade` | 2050 cap | config ready (2% of 1990, placeholder) |
| `trade-cable-cap2050-relaxed` | `trade-cap2050-relaxed` | the cable | config ready, waits as above |

Island comparison, layered on the workshop config only:

| Run | Differs from | in | Status |
|---|---|---|---|
| `de10-myopic` | – | baseline | solved |
| `cable` | `de10-myopic` | the cable (role 1 central) | config ready, waits as above |
| `cable-cost-low`, `cable-cost-high` | `cable` | role 1 low / high level | config ready, waits as above |
| `cable-project` | `cable` | asset WACC and IDC from `financing.py` instead of 7% | to do: private layer for role 1's parameter file |
| `cap2050-relaxed` | `de10-myopic` | 2050 cap | solved (2% of 1990, placeholder) |
| `cable-cap2050-relaxed` | `cable` | 2050 cap | config ready, waits as above |

Border trade prices the neighbours at their 2024 level plus 7% per horizon
(group decision), and imports carry the neighbours' 2024 CO2 intensity into
the German cap. With `co2_scaling` at 1.0 in every horizon, the zero cap of
2050 leaves almost no room for imports, so 2050 stays as tight as in the
island model. How fast the neighbours decarbonise (`co2_scaling`) is a role 4
decision still to make; `price_scaling` and `net_import_limit` are the other
levers for a sensitivity once the main runs stand.

The cable configs turn on role 1's code with `brazil_cable: {enable: true,
level: ...}` (`workshop/cable/add_brazil_cable.py`). Commissioning 2040 and
4 GW as in role 1's central case; build year (2035/2045) and size (2/6 GW) are
the next sensitivities if time allows. The main runs use the harmonised 7%;
project finance is a sensitivity (`cable-project`).

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

## Screening before the model run (`workshop/economics/screening.py`)

Until the cable is in the model, a per-MW screening answers whether it can pay
at all: cost of a MWh delivered to Wilhelmshaven (RN wind + cable + losses)
against its value there (hourly price at `DE0 7AC` in the runs without the
cable, an upper bound because it ignores that the cable lowers those prices).
It reads at runtime role 1's cable parameters (investment, FOM, lifetime,
end-to-end efficiency, availability per level and route) and role 2's RN wind
profile; wind costs are the public PyPSA-Eur `onwind` entry until role 2
delivers. Public variant to `results/economics/screening/`; project-finance
variant to `workshop/private/`.

```bash
pixi run python workshop/cable/cable_route.py
pixi run python workshop/cable/cable_cost.py
pixi run python workshop/brazil/build_rn_onwind_profile.py
pixi run python workshop/economics/screening.py
```

First result (reference route, wind sized to the cable, 7%, run without the
cable): a MWh delivered costs about 670 / 1,200 / 2,600 EUR at role 1's low /
central / high cable cost, against a value of 90–112 EUR/MWh. The cable would
have to cost 4–7% of role 1's central to low estimate to pay. Main drivers:
the cable is used 35% of the time (wind only) and the investment per MW. 2050
does not change the picture: the RN wind does not blow in the German price
peaks. Oversizing the wind 1.5x lowers the cost by about 30%.

## Inputs from the other roles (status)

| From | What | Where | Used in |
|---|---|---|---|
| Role 1 | landing points Natal (RN) and Wilhelmshaven, node `DE0 7AC` | `workshop/cable/cable_route.py` | screening |
| Role 1 | route lengths and depth per case (reference via the Channel, shortest/deep, around Scotland, Sines) | `results/cable/cases.csv` | screening |
| Role 1 | cable cost, losses, availability, lifetime per level; size range 2/4/6 GW; build year 2040 (2035–2045) | `workshop/cable/cable_parameters.yaml` | screening, cable configs |
| Role 2 | hourly RN onshore wind capacity factor, 2013, UTC | `resources/brazil/rn_onwind_cf_2013_utc.csv` | screening |
| Role 2 | Brazilian costs (CAPEX, FOM, VOM), solar | _open_ | |
| Role 3 | decision on 2050 | _open_ | |
| Role 1 | the cable in `compose_network` | `workshop/cable/add_brazil_cable.py` | all cable runs |
| Role 2 | Brazilian generators at `Brazil Natal` in `compose_network` | _open, role 2 (Julian) took it on_ | all cable runs |
| Role 3 | border trade with the neighbours | `scripts/add_border_trade.py`, `config/workshop/border-trade.yaml` | all main runs |

## What the other roles deliver

- **Role 1:** the cable as a link whose name contains `Brazil` (the evaluation
  and the plot style recognise it by that), its capacity, cost and
  commissioning year, all in EUR at the price base above.
- **Role 2:** Brazilian supply as components whose names contain `Brazil`,
  costs in EUR at the agreed rate.
- **Role 3:** the decision on 2050 and whether the German model is good enough
  to judge the cable; how long a run takes.

## Hand-over for the model code (`compose_network`)

What the evaluation expects once the cable and Brazil are added, so that
`analyse_runs.py` and the plot style recognise them:

- one AC bus `Brazil Natal` (role 1's proposal), with `country: BR`;
- the cable as a link from the Brazil bus to `DE0 7AC`, name and carrier
  containing `Brazil` (role 1 uses the carrier `Brazil cable`), efficiency and
  `p_max_pu` from role 1's level, Brazil to Germany only;
- Brazilian generators at the Brazil bus with names containing `Brazil` and the plain technology as carrier,
  profile from role 2;
- capital costs: `financing: project` uses `financing.load()` at runtime
  (`idc_factor` and `wacc` per asset); `financing: harmonised` uses the
  model's default discount rate. No value from the term sheet in code or
  config.
- added from role 1's build year on (`brazil_cable` block, role 1's code).
