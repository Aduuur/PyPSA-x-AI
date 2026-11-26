<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Role 1: Cable techno-economics

## Goal

A comprehensive assessment of the cable: where it is laid, at what cost, under
which constraints, with what lifetime and financing. The result has to be
usable as input to the model.

## What you start with

- Atlantic bathymetry in `data-brazil/bathymetry_atlantic/`: the whole corridor
  at coarse resolution, and the areas off north-east Brazil and in the North Sea
  at full resolution.
- The HVDC entries in the model's cost tables
  (`data/costs/archive/v0.15.0/costs_<year>.csv`: `HVDC submarine`,
  `HVDC inverter pair`). They describe European sea cables and are a reference
  point, not an answer for the Atlantic.
- The background slide of the introduction: the longest and deepest cables
  built so far, and the studies of similar links.

## What you are responsible for

- The route, both landing points and the resulting length.
- The depth profile and what it means for the design. Cables have been laid at
  2,150 m and qualified for 3,000 m; this route reaches about 6,000 m.
- Cost: cable, converter stations, laying, and losses over the distance.
- Lifetime, construction time and financing: cost of capital and who carries
  which risk.
- Constraints and risks: repair and availability, seabed ecology, politics.
- The cable's size, or the range of sizes worth studying.

## Coordinate with

- **Role 2:** the Brazilian landing point follows from the region they choose,
  and it sets your route and length. Decide it together, early.
- **Role 3:** the German node the cable connects to.
- **Roles 2 and 3:** your contribution to the model lands in
  `scripts/compose_network.py`, where theirs lands too. Agree with them how.
- **Role 4:** the economic parameters every role uses, and which of your
  numbers they need to vary between scenarios.

## Guardrails

- Every number has a source and a year. Say where you extrapolate beyond what
  has been built.
- Give ranges, not single values: this cable has no precedent.
- The model turns investment costs into annual costs itself, from a lifetime
  and a discount rate. Check how before you hand over costs.
- An assessment that finds the cable infeasible or unaffordable is a valid
  result. State what would have to change.
