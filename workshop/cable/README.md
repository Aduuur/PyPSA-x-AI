<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Cable (role 1): Natal–Wilhelmshaven HVDC

Hand-over to roles 2, 3 and 4. Status: first version, public assumptions only.

## Requests to other roles (open)

Please answer by editing this table (or the section in your own README) and
pushing to `main`. Details further below.

| # | To | Request | Status |
|---|---|---|---|
| 1 | Role 2 | Create the Brazilian AC bus `Brazil Natal` (`carrier: AC`, `country: BR`) and attach your RN supply to it, or tell me your bus name and I set `bus_brazil`. Until it exists the cable adds an empty bus there, so the cable carries no power. | agreed (role 2): bus `Brazil Natal` (`carrier: AC`, `country: BR`) at the Natal coordinates; role 2 creates it and attaches the RN supply; `bus_brazil` stays at its default |
| 2 | Role 2 | If you add Brazil in `scripts/compose_network.py`, put your call **before** the cable call (marked `Workshop: Brazil-Germany cable (Role 1)`), so the bus exists when the cable is added. | agreed (role 2): role 2's call goes into `scripts/compose_network.py` before the cable call, in its own file under `workshop/brazil/`, off by default |
| 3 | Role 2 | Your README gives ~73 km from the RN cells to the coast. The cable cost covers the sea route only; the onshore connection from your sites to the converter at Natal is yours (or tell me if I should add it). | agreed (role 2): role 2 takes the onshore connection from the generators to the converter at Natal; the cable cost stays sea route plus converters |
| 4 | Role 3 | Confirm `DE0 7AC` (nearest node to Wilhelmshaven) as the German node. | open |
| 5 | Role 3 | Does the German grid at `DE0 7AC` need reinforcement for 4 GW (6 GW in the high case)? | open |
| 6 | Role 3 | The 2050 decision: the cable result in 2050 depends on it (see `workshop/README.md`). | open |
| 7 | Role 4 | Scenario mapping is in `cable_parameters.yaml`: `cable` = central, `cable-cost-low` = low, `cable-cost-high` = high. Turn the cable on with `brazil_cable: {enable: true, level: ...}` in the scenario config. | done (role 4): `config/workshop/cable.yaml`, `cable-cost-low.yaml`, `cable-cost-high.yaml`, `cable-cap2050-relaxed.yaml` use `brazil_cable: {enable: true, level: ...}` |
| 8 | Role 4 | Commissioning 2040 central (2035–2045), size 4 GW (2–6 GW worth studying). Confirm, or say which of these you want to vary. | confirmed (role 4): 2040 and 4 GW in all main runs; build year 2035/2045 and 2/6 GW are the next sensitivities if time allows |
| 9 | Role 4 | `cable-wacc`: set `brazil_cable.discount_rate` in that scenario; it overrides the harmonised 7 % for the cable only. | answered (role 4): the main runs keep the harmonised 7 %. The project-finance rate is derived from a confidential document, so it must not go into a shared scenario config; role 4 passes it as an extra config layer from `workshop/private/` (`cable-project`). No change needed in your code. |
| 10 | Whoever maintains `workshop/guard/` | The guard crashes on binary files (PNG, PDF) and flags coordinate digits in the route map SVG/GeoJSON (public GEBCO data). Please make it skip binary files; then the PNG/PDF figures can be shared. Details and a suggested fix: section "Request to the guard maintainer" below. Role 1 needs the route map. | with the group (role 4): `workshop/guard/` is protected by the group's rules, so it is not changed by an agent; the decision is with the person maintaining it |
| 11 | Roles 3, 4 | Risk assessment in [RISKS.md](RISKS.md): the model cannot show N-1 security, sabotage or political interruption. Please count the cable as energy, not as secured capacity, and discuss the risk-sharing table with role 4 (financing). | open |

## Request to the guard maintainer: route map blocked

Role 1 needs to share the cable route map (`routes_map.png` / `.pdf`), made from
public data only (GEBCO_2025 bathymetry and public town coordinates). The guard
blocks it in every format, and nobody may bypass it, so it needs a fix by the
person who maintains `workshop/guard/`:

1. **Binary files crash the guard.** `confidential_guard.py staged` runs
   `git diff --cached --text` and decodes the output as UTF-8; a PNG or PDF in
   the commit raises `UnicodeDecodeError` and the commit is blocked. Suggested
   fix: leave out binary files (`git diff --cached --numstat` shows `-` for
   them, or check for a NUL byte), or decode with `errors="replace"`.
   Then any PNG/PDF figure can be committed. Note that a binary file is then not
   scanned; if the group wants images checked too, that needs a separate rule
   (for example: figures only from scripts in the repo).
2. **Possible false matches in the map SVG.** The SVG of the map holds
   thousands of numbers (path coordinates of the bathymetry); the guard reports
   5 matches against one role's confidential file. The map contains no
   confidential data, so these are most likely coincidental numbers. Please
   check them with the guard's owner of that file (role 2), without
   showing the values.

Once 1 is fixed, role 1 commits `workshop/cable/results/routes_map.png` and the
other PNG/PDF figures. Until then the map is shared outside git, or anyone can
build it with `pixi run python workshop/cable/cable_route.py` (about 3 minutes).

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
| `risk_exposure.csv`, `risk_exposure_by_eez.csv` | measured risk exposure per case: shelf, depth, slope, km per country's waters |
| `depth_profile.svg`, `cost_breakdown.svg`, `risk_matrix.svg` | figures |

Risk assessment: [RISKS.md](RISKS.md) (register in `risk_register.csv`).

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
