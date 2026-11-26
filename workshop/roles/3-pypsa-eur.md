<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Role 3: PyPSA-Eur setup

## Goal

Make sure the baseline is sensible, understand and explain what the model is
doing, and refine it. The aim is a model good enough that the feasibility of
the cable can be judged against an accurate system.

## What you start with

- The baseline: its config (`config/config.workshop.yaml`), the six solved
  networks and what they assume, all described in [BASELINE.md](../BASELINE.md).
- The raw European data in `data/`, from which the inputs can be rebuilt.

## What you are responsible for

- Knowing what the model does in every planning year, and being the person in
  your group who can explain a result.
- Checking every solved year against what is plausible.
- Improving the model where it matters for the cable. The main shortcoming:
  **Germany has no imports or exports.** It is modelled as an island, so
  scarcity that trade would cover shows up as storage, backup plants and high
  prices. The challenge is to address this and the other shortcomings (see
  "Known limitations" in BASELINE.md) within the computational and time
  constraints of the day.

## The 2050 problem

The CO₂ cap falls to zero in 2050. In the baseline the cap then adds about
24,000 €/t on top of the CO₂ price, and electricity prices peak near
3,000 €/MWh. Against that, any clean power looks enormously valuable, the cable
included. A model-side answer is yours to find; whether 2050 stays in the study
is role 4's call. Decide together.

## Coordinate with

- **Roles 1 and 2:** the German node the cable connects to, and the code that
  adds Brazil and the cable. All three of you change
  `scripts/compose_network.py`. Agree how.
- **Role 4:** they set the study design and vary assumptions between
  scenarios. Make what you refine reachable from config files, so they can.

## Guardrails

- Keep the original baseline reproducible. Compare every refinement against it,
  one change at a time.
- A workspace is stopped when it runs out of memory, and a day has few solves
  in it. Measure memory and run time of a change before your group depends on
  it; BASELINE.md has the baseline's figures.
- Give a source for every assumption you change.
- A more detailed model is not automatically a more accurate one. Prefer the
  change that most affects how the cable is valued.
