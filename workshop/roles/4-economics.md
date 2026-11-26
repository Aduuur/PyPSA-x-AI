<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Role 4: Economic analysis

## Goal

The most overarching role: you determine the study design and show what the
cable is worth, and to whom. You work in config files and postprocessing, not
in model code.

## What you start with

- The baseline config (`config/config.workshop.yaml`) and its six solved
  networks in `results/de10-myopic/networks/`; see [BASELINE.md](../BASELINE.md).
- The baseline's economic settings in `config/config.default.yaml` under
  `costs` (discount rate, cost tables, overwrites).

## What you are responsible for

- **The study design.** Is this a capacity expansion study, in which the model
  decides whether and how much cable to build, or a cost-benefit analysis of a
  given cable? Which planning years and which time horizon? What is compared
  with what?
- **Harmonised economic parameters.** Discount rate, cost year, currency,
  lifetimes: one set for Germany, Brazil and the cable, which every role uses.
- **The scenarios.** Runs with and without the cable, plus the sensitivities
  that matter, each as a config file layered on the baseline.
- **The results.** One postprocessing pipeline over all runs: system cost,
  flows on the cable, prices, emissions, and who gains and who loses. It
  produces the figures for the final presentation.

## The 2050 problem

The CO₂ cap falls to zero in 2050. In the baseline the cap then adds about
24,000 €/t on top of the CO₂ price, and electricity prices peak near
3,000 €/MWh. Against that, any clean power looks enormously valuable, the cable
included. Whether and how 2050 enters your result is a design decision; a
model-side answer is role 3's to find. Decide together.

## Coordinate with

- **Everyone:** your design decisions bind the other roles, so make them early
  and make them known.
- **Roles 1 and 2:** they supply the costs of the cable and of Brazilian power.
  You make sure these are comparable with each other and with the German ones.
- **Role 3:** which assumptions can be varied from config files, and how long a
  run takes. That limits how many scenarios fit in the day.

## Guardrails

- Two runs you compare differ in one thing only.
- Build the results pipeline on the baseline first, before any cable run
  exists.
- No run may overwrite another. A scenario with its own run name needs its own
  inputs; BASELINE.md says what that takes.
- The brief is to show the cable is an amazing solution. Report what the
  result depends on, also where it does not hold.
