<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Cable (role 1): Natal–Wilhelmshaven HVDC

Hand-over to roles 2, 3 and 4. Status: first version, public assumptions only.

## Agreed

| | |
|---|---|
| Brazilian landing point | Natal region, Rio Grande do Norte (with role 2) |
| German landing point and node | Wilhelmshaven, model node `DE0 7AC` (group decision) |
| Reference route | depth-aware, via the English Channel: **9,275 km**, max depth 4,720 m |

## Results (in `results/`, tracked)

| File | Content |
|---|---|
| `route_cases.csv` | the four route cases: length, max depth, km deeper than 3,000 / 5,000 m |
| `routes_all.csv` | all computed routes (3 Brazilian x 2 German landing points x 4 variants + Sines) |
| `depth_profiles_10km.csv` | water depth along the four cases, every 10 km |
| `cost_estimate.csv` | cost, losses, availability for every case and level (low / central / high) |
| `depth_profile.svg`, `cost_breakdown.svg` | figures |

PNG and PDF versions, the route map and the route geometry are written to
`results/cable/` (git-ignored) when you run the scripts. Run them yourself to
get them (about 3 minutes):

```bash
pixi run python workshop/cable/cable_route.py
pixi run python workshop/cable/cable_cost.py
```

Why the map and route lines are not committed: the group's NDA guard
(`workshop/guard/`) cannot read binary files (PNG, PDF) and flags long runs
of coordinate digits in the map SVG and GeoJSON as possible matches with
confidential files. They contain only public GEBCO data, but the guard is not
bypassed. Fixing the guard is with whoever maintains it.

### Key figures, reference route, 4 GW

| | low | central | high |
|---|---|---|---|
| Investment, million EUR per MW | 17.4 | 30.4 | 59.2 |
| Investment for 4 GW, billion EUR | 70 | 121 | 237 |
| End-to-end efficiency | 0.898 | 0.856 | 0.790 |
| Availability | 0.948 | 0.846 | 0.691 |
| Lifetime, years | 40 | 40 | 30 |
| Transmission cost at full use, EUR/MWh | 233 | 478 | 1,304 |

Cable (incl. depth premium) is about 2/3 of the cost, converters under 3 %.
About 2,400 km of the route lie deeper than the deepest qualified cable
(3,000 m): this is the main technical risk. Sources and assumptions are in
`cable_cost.py`; values marked `verify` there still need checking against the
original publication.

## Proposal for roles 2 and 3: how the cable enters the model

To agree. The cable code lives in its own file, `add_brazil_cable.py`;
`scripts/compose_network.py` only gets one small call near the end, after
brownfield and the first-horizon freeze, before the sanity checks. Roles 2 and
3 can add their own calls next to it without touching each other's code.

- **Switch:** off by default, so the baseline is unchanged. A scenario turns
  it on in its config:

  ```yaml
  brazil_cable:
    enable: true
    level: central        # low | central | high -> cable / cable-cost-low / cable-cost-high
    # p_nom: 4000         # MW, default from cable_parameters.yaml
    # build_year: 2040
    # bus_brazil: Brazil Natal
  ```

- **One link** `Brazil cable`, carrier `Brazil cable`, from `bus_brazil` to
  `DE0 7AC`, Brazil to Germany only, fixed size, built in `build_year` and kept
  in every later horizon (myopic brownfield carries it over).
- **Costs** are annualised like in `scripts/process_cost_data.py`:
  (annuity(lifetime, discount rate) + FOM) x investment. Discount rate from
  `costs.fill_values` (7 %, role 4) unless `brazil_cable.discount_rate` is set
  (for `cable-wacc`).
- **Efficiency** is end to end (converters + cable); **p_max_pu** is the mean
  availability.

**Role 2:** please create the Brazilian AC bus named `Brazil Natal` (or tell me
your name and I set `bus_brazil`), with `country: BR`, and attach your supply
to it. Until it exists, the cable adds a bare bus there, so the cable carries
no power. If you add your components in `compose_network.py` too, please call
them before the cable.

**Role 3:** please confirm `DE0 7AC` as the German node, and whether the German
grid needs reinforcement there for 4 GW.

**Role 4:** `cable_parameters.yaml` has the three levels and the scenario
mapping. Commissioning 2040 central (range 2035–2045); size 4 GW central,
2–6 GW worth studying.
