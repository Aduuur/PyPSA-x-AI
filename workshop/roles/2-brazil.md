<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Role 2: Brazil renewable potential

## Goal

Find where in Brazil, and with which renewables, power for the cable is best
produced, and what it costs.

## What you start with

Prepared files in `data-brazil/`, for weather year 2013. Read
`data-brazil/README.md` first: it maps every file and the traps in the data.

| Folder | Content |
|---|---|
| `weather/` | ERA5 weather cutout for Brazil (wind, solar radiation, temperature, runoff), hourly |
| `layers/` | land cover, protected areas, elevation and sea depth, ship density, exclusive economic zone, cut to Brazil |
| `raw/ons/` | grid operator data: load, hydro inflow and reservoir levels, generation by plant, flows between subsystems, plant register, lines |
| `raw/obed/` | state-level plants, grid, inflow and hourly demand (DLR Open Brazilian Energy Data) |
| `raw/gadm/`, `raw/wri/` | state borders, global power plant database |
| `bathymetry_atlantic/` | sea depth for the cable route (role 1) |

Nothing in it is a model yet.

## What Brazil is in this study

By default, Brazil is a dedicated export site: new renewable plants at the
cable's landing point whose only customer is the cable. There is no Brazilian
demand and no Brazilian grid in the model.

You can go deeper and assess whether integration with the actual Brazilian
system, with its demand, its hydro reservoirs and its existing plants, is the
better economic proposition.

## What you are responsible for

- The region: scope Brazil for where production for export is most suitable.
- The technologies: which renewables should be built there.
- Their potential and their hourly availability.
- Their cost. Whatever you find has to be expressed as CAPEX, FOM and VOM, the
  terms the model's cost tables use
  (`data/costs/archive/v0.15.0/costs_<year>.csv`).

## Coordinate with

- **Role 1:** your choice of region sets the landing point, and with it the
  length and geography of the cable. Decide it together, early.
- **Roles 1 and 3:** if you contribute code to the model, it lands in
  `scripts/compose_network.py`, where theirs lands too. Agree with them how.
- **Role 4:** the economic parameters every role uses, so that Brazilian costs
  are comparable with the German ones.

## Guardrails

- Derive Brazilian costs the way the European ones are derived. A cost
  advantage that comes from mixing cost years, currencies or discount rates is
  not a result.
- Check your profiles against what the grid operator measured (`raw/ons/`).
- The weather file is 5.8 GB. Work on the region you need, not on all of Brazil
  at once: your workspace is stopped when it runs out of memory.
- GADM and WDPA must not be redistributed. Keep the data within the workshop.
