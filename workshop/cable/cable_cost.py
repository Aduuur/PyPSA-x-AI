# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Cost, losses and availability of the Brazil-Germany HVDC cable (Role 1).

Builds a low / central / high estimate for each route case of
``cable_route.py`` (reads ``results/cable/cases.csv`` and
``results/cable/profiles.csv``; run that script first) and writes
model-ready parameters.

Public assumptions only. Every number below carries a source and a year, or
is marked as a Role 1 assumption / extrapolation beyond anything built. Values
marked ``verify`` come from public project reporting quoted from memory and
must be checked against the original source before they go on a slide.
Confidential inputs (``workshop/inputs/``) are not read here; a private layer
can override these parameters at runtime (see ``PRIVATE_OVERRIDE``).

How the model annualises (checked in scripts/process_cost_data.py):
    capital_cost = (annuity(lifetime, discount rate) + FOM/100) * investment
with annuity(n, r) = r / (1 - (1 + r)^-n) and the discount rate from the cost
data or ``costs.fill_values`` (7%, harmonised by Role 4). So we hand over the
*overnight investment* in EUR/MW, FOM in %/a and lifetime, not annual costs.

Outputs:
  results/cable/cost_estimate.csv        all components, cases and ranges
  workshop/cable/cable_parameters.yaml   model-ready parameters (public)
  results/cable/cost_breakdown.png/.pdf  figure

Run from the repo root (after cable_route.py):

    pixi run python workshop/cable/cable_cost.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "workshop/plotstyle").is_dir())
sys.path.insert(0, str(ROOT / "workshop/plotstyle"))
import studystyle as st  # noqa: E402

OUT = ROOT / "results/cable"
PARAMS = ROOT / "workshop/cable/cable_parameters.yaml"
PRIVATE_OVERRIDE = ROOT / "workshop/private/cable_parameters_private.yaml"  # git-ignored
COSTS = ROOT / "data/costs/archive/v0.15.0/costs_{year}.csv"

LEVELS = ["low", "central", "high"]  # low = optimistic (cheap), high = pessimistic

# --------------------------------------------------------------------------
# Assumptions. (low, central, high)
# --------------------------------------------------------------------------
# Cost levels vary cost, losses, availability and lifetime only. Size and
# commissioning year stay fixed across them, so the Role 4 scenarios
# cable / cable-cost-low / cable-cost-high differ in one thing only.
COMMISSIONING = 2040
COMMISSIONING_RANGE = (2035, 2045)
# Earliest 2035 per Role 4 study design. 2040 central: Role 1 assumption from
# the ~9,300 km of cable to be made, several years of global HVDC submarine
# cable production at today's capacity; manufacturing slots are booked years ahead.

CAPACITY_MW = 4000
SIZES_MW = [2000, 4000, 6000]
# Range of sizes worth studying (Role 1 assumption): one bipole of 2 GW
# (+-525 kV class) up to three; 4 GW central. Costs are per MW and assumed
# linear in capacity (simplification; real projects have economies of scale).

DEA_COST_YEAR = 2035  # cost-data year matching the earliest commissioning year

# Cable, EUR/MW/km, including manufacturing and installation in shelf depths.
# high = DEA, Technology Data for Energy Transport (July 2025), "HVDC submarine",
#        in data/costs/archive/v0.15.0/costs_<year>.csv, EUR 2025.
# central/low = all-in cost per MW and km of recent long interconnectors, which
#        come out below DEA (higher voltage, larger capacity). verify:
#        NordLink 2020 (1.4 GW, ~620 km, ~EUR 2 bn), Viking Link 2023 (1.4 GW,
#        ~765 km, ~GBP 1.8 bn), Xlinks Morocco-UK (planned, 3.6 GW, ~3,800 km,
#        ~GBP 20-24 bn). These figures include converters, so they are an upper
#        bound for the cable-only value used here.
CABLE_EUR_PER_MW_KM = {"low": 1500, "central": 2200, "high": None}  # None -> DEA value

# Depth premium on the cable cost per km, by depth band (Role 1 assumption,
# extrapolation): heavier/lighter-weight designs, mechanical tension during
# laying, special vessels, slower laying, fewer suppliers. Reference depths:
# deepest laid 2,150 m, deepest qualified 3,000 m (role brief, intro slide).
DEPTH_BANDS_M = [0, 2150, 3000, 99999]
DEPTH_MULT = {  # band: (low, central, high)
    "<= 2,150 m (built)": (1.0, 1.0, 1.0),
    "2,150-3,000 m (qualified)": (1.1, 1.25, 1.5),
    "> 3,000 m (no precedent)": (1.3, 1.6, 2.5),
}

# Converter pair (both ends), EUR/kW. central = DEA "HVDC inverter pair"
# (July 2025, EUR 2025) for the cost-data year; low/high = -10% / +50%
# (Role 1 assumption: converter prices in recent tenders 2022-2024 rose
# well above earlier cost data; verify against TSO tender reporting).
CONVERTER_FACTOR = {"low": 0.9, "central": 1.0, "high": 1.5}

# Contingency on cable + converters for a first-of-a-kind project
# (Role 1 assumption; common practice 10-30% for megaprojects).
CONTINGENCY = {"low": 0.10, "central": 0.20, "high": 0.35}

# Fixed O&M, %/a of investment. DEA: cable 2.5, converter 1.5 (July 2025).
# Kept for all levels; repairs are covered by availability below.
FOM_CABLE, FOM_CONV = 2.5, 1.5

# Lifetime, years. DEA: 40 for cable and converter (July 2025).
# high = 30 (Role 1 assumption: deep-water cable, no track record).
LIFETIME = {"low": 40, "central": 40, "high": 30}

# Losses. Converter: ~0.7-1.0% per station (VSC; verify, manufacturer data).
# Cable: % of rated power per 1000 km at full load. Physics check, Role 1:
# +-800 kV, 2 GW bipole, 3000 mm2 Cu: I^2R ~0.9%/1000 km; +-525 kV: ~2.1%.
# high = PyPSA-Eur default for DC links (config.default.yaml,
# transmission_efficiency.DC: 0.977 per 1000 km, 0.98 static).
CONV_EFF_PER_STATION = {"low": 0.993, "central": 0.9925, "high": 0.99}
CABLE_LOSS_PER_1000KM = {"low": 0.010, "central": 0.015, "high": 0.023}

# Availability from faults and repair (Role 1 assumption; order of magnitude
# from CIGRE TB 379 (2009) on submarine cable failure statistics: verify).
# Faults per 100 km and year; repair days. Shallow (< 200 m: anchors,
# fishing) fails more often; deep water fails rarely but takes longer to repair.
FAULTS_SHALLOW = {"low": 0.01, "central": 0.02, "high": 0.03}
FAULTS_DEEP = {"low": 0.002, "central": 0.005, "high": 0.008}
REPAIR_DAYS_SHALLOW = {"low": 30, "central": 45, "high": 60}
REPAIR_DAYS_DEEP = {"low": 60, "central": 90, "high": 120}
PLANNED_OUTAGE = 0.01  # share of the year, Role 1 assumption

DISCOUNT_RATE = 0.07  # harmonised (Role 4, STUDY_DESIGN.md); cable-wacc varies it
UTILISATION = 0.6  # for the indicative cost per MWh only; the model sets the flow


def dea(technology, parameter, year=DEA_COST_YEAR):
    df = pd.read_csv(str(COSTS).format(year=year))
    row = df[(df.technology == technology) & (df.parameter == parameter)]
    return float(row.value.iloc[0])


def annuity(n, r):
    return r / (1 - (1 + r) ** -n) if r > 0 else 1 / n


def km_by_band(profile):
    step = np.diff(np.r_[profile.km.values, profile.km.values[-1] + 2.0])
    bands = pd.cut(profile.depth_m, DEPTH_BANDS_M, labels=list(DEPTH_MULT), right=True,
                   include_lowest=True)
    out = pd.Series(step, index=profile.index).groupby(bands, observed=False).sum()
    return out.reindex(list(DEPTH_MULT)).fillna(0.0)


def estimate(case, route_km, bands, shallow_km, level):
    i = LEVELS.index(level)
    base = CABLE_EUR_PER_MW_KM[level] or dea("HVDC submarine", "investment")
    cable_built = base * bands.iloc[0] * DEPTH_MULT[bands.index[0]][i]
    depth_premium = sum(base * bands[b] * (DEPTH_MULT[b][i] - 1) for b in bands.index)
    cable_qual_deep = base * bands.iloc[1:].sum()
    cable = cable_built + cable_qual_deep + depth_premium  # EUR/MW
    conv = dea("HVDC inverter pair", "investment") * 1e3 * CONVERTER_FACTOR[level]  # EUR/kW -> EUR/MW
    cont = CONTINGENCY[level] * (cable + conv)
    inv = cable + conv + cont
    fom = (FOM_CABLE * (cable + CONTINGENCY[level] * cable)
           + FOM_CONV * (conv + CONTINGENCY[level] * conv)) / inv  # weighted %/a
    eff = CONV_EFF_PER_STATION[level] ** 2 * (1 - CABLE_LOSS_PER_1000KM[level]) ** (route_km / 1000)
    deep_km = route_km - shallow_km
    down_days = (shallow_km / 100 * FAULTS_SHALLOW[level] * REPAIR_DAYS_SHALLOW[level]
                 + deep_km / 100 * FAULTS_DEEP[level] * REPAIR_DAYS_DEEP[level])
    avail = max(0.0, 1 - down_days / 365 - PLANNED_OUTAGE)
    life = LIFETIME[level]
    cap_cost = (annuity(life, DISCOUNT_RATE) + fom / 100) * inv  # EUR/MW/a, as the model does it
    mw = CAPACITY_MW
    mwh = 8760 * UTILISATION * avail * eff  # delivered per MW and year
    return dict(
        case=case, level=level, length_km=route_km, capacity_MW=mw,
        commissioning=COMMISSIONING,
        cable_EUR_per_MW_km_base=base,
        **{f"km {b}": bands[b] for b in bands.index},
        cable_EUR_per_MW=cable_built + cable_qual_deep, depth_premium_EUR_per_MW=depth_premium,
        converter_EUR_per_MW=conv, contingency_EUR_per_MW=cont, investment_EUR_per_MW=inv,
        investment_bnEUR=inv * mw / 1e9, FOM_pct=fom, lifetime_a=life,
        efficiency=eff, availability=avail, outage_days=down_days,
        capital_cost_EUR_per_MW_a_at_7pct=cap_cost,
        annual_cost_bnEUR_at_7pct=cap_cost * mw / 1e9,
        transmission_cost_EUR_per_MWh=cap_cost / mwh,
    )


def main():
    cases = pd.read_csv(OUT / "cases.csv", index_col=0)
    prof = pd.read_csv(OUT / "profiles.csv")
    rows = []
    for case, r in cases.iterrows():
        p = prof[prof.route == r.route]
        bands = km_by_band(p)
        shallow = float(np.diff(np.r_[p.km.values, r.length_km])[p.depth_m.values <= 200].sum())
        for level in LEVELS:
            rows.append(estimate(case, r.length_km, bands, shallow, level))
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "cost_estimate.csv", index=False)

    show = ["investment_EUR_per_MW", "investment_bnEUR", "efficiency", "availability",
            "capital_cost_EUR_per_MW_a_at_7pct", "transmission_cost_EUR_per_MWh"]
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", lambda v: f"{v:,.3f}" if abs(v) < 10 else f"{v:,.0f}")
    print(df.set_index(["case", "level"])[show].to_string())
    ref = df[df.case == "reference"].set_index("level")
    print("\nInvestment of the reference route by size, bn EUR:")
    print(pd.DataFrame({f"{mw / 1e3:.0f} GW": ref.investment_EUR_per_MW * mw / 1e9 for mw in SIZES_MW})
          .loc[LEVELS].round(0).to_string())

    write_parameters(df)
    plot(df)


def write_parameters(df):
    """Model-ready parameters for the reference route (public assumptions).
    compose_network reads this file; a private layer may override it."""
    ref = df[df.case == "reference"].set_index("level")
    alt = df[df.case != "reference"].set_index(["case", "level"])
    out = {
        "description": "Brazil-Germany HVDC cable, Role 1. Public assumptions; see "
                       "workshop/cable/cable_cost.py for sources. EUR at the price base of the cost data.",
        "bus_brazil": "Natal region (node from Role 2)",
        "bus_germany": "DE0 7AC",
        "carrier": "Brazil cable",
        "length_km": float(ref.loc["central", "length_km"]),
        "p_nom_MW": CAPACITY_MW,
        "sizes_worth_studying_MW": SIZES_MW,
        "build_year": COMMISSIONING,
        "build_year_range": list(COMMISSIONING_RANGE),
        "discount_rate_used_for_checks": DISCOUNT_RATE,
        "levels": {
            lvl: {
                "investment_EUR_per_MW": round(float(ref.loc[lvl, "investment_EUR_per_MW"]), -3),
                "FOM_pct_per_a": round(float(ref.loc[lvl, "FOM_pct"]), 2),
                "lifetime_a": int(ref.loc[lvl, "lifetime_a"]),
                "efficiency": round(float(ref.loc[lvl, "efficiency"]), 3),
                "p_max_pu": round(float(ref.loc[lvl, "availability"]), 3),
            }
            for lvl in LEVELS
        },
        "scenarios": {  # which level each Role 4 scenario uses
            "cable": "central", "cable-cost-low": "low", "cable-cost-high": "high",
        },
        "route_alternatives_investment_EUR_per_MW": {
            c: {lvl: round(float(alt.loc[(c, lvl), "investment_EUR_per_MW"]), -3) for lvl in LEVELS}
            for c in df.case.unique() if c != "reference"
        },
        "notes": [
            "investment is overnight cost; the model annualises it with the discount rate "
            "(7% harmonised) and adds FOM (scripts/process_cost_data.py).",
            "efficiency is end to end (both converters + cable) at full load, applied as a "
            "linear PyPSA link efficiency; losses in the reverse direction need a second link "
            "or a single direction (flow Brazil -> Germany).",
            "p_max_pu is mean availability from faults, repair and planned outages, applied as a derating.",
            "Several bipoles fail independently; with 2+ bipoles a fault takes out only part of the capacity.",
        ],
    }
    PARAMS.write_text("# Generated by workshop/cable/cable_cost.py. Do not edit by hand.\n"
                      + yaml.safe_dump(out, sort_keys=False, allow_unicode=True))
    print(f"\nwrote {PARAMS.relative_to(ROOT)}")


def plot(df):
    st.use()
    cable = st.GROUPS["Brazil cable"]
    ref = df[df.case == "reference"].set_index("level").loc[LEVELS]
    parts = pd.DataFrame({
        "Cable": ref.cable_EUR_per_MW,
        "Depth premium": ref.depth_premium_EUR_per_MW,
        "Converters": ref.converter_EUR_per_MW,
        "Contingency": ref.contingency_EUR_per_MW,
    }) / 1e6  # million EUR per MW
    colors = {"Cable": (cable, 1), "Depth premium": (cable, st.TINT), "Converters": (st.TEXT, 1),
              "Contingency": (st.NEUTRAL, 1)}
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(5.6, 3.4), width_ratios=[1.25, 1])
    x = np.arange(len(LEVELS))
    bottom = np.zeros(len(LEVELS))
    for col in parts:
        c, al = colors[col]
        a1.bar(x, parts[col], bottom=bottom, width=0.62, color=c, alpha=al, edgecolor="white",
               linewidth=0.6, zorder=2)
        bottom += parts[col].values
    for xi, t in zip(x, bottom):
        a1.annotate(f"{t:,.0f}", (xi, t), xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=7.5, color=st.TEXT)
    a1.set_xticks(x, LEVELS)
    a1.set_ylim(0, bottom.max() * 1.25)
    a1.set_title("Investment, million EUR per MW", loc="left")
    st.legend_squares(a1, [(colors[k][0], k, colors[k][1]) for k in parts.columns][::-1],
                      loc="upper left", fontsize=7)

    lcot = ref.transmission_cost_EUR_per_MWh
    st.bars(a2, x, lcot.values, color=cable)
    a2.set_xticks(x, LEVELS)
    a2.set_ylim(0, lcot.max() * 1.2)
    a2.set_title("Transmission cost, EUR/MWh", loc="left")
    fig.suptitle("Brazil cable Natal-Wilhelmshaven, 9,275 km", x=0.01, ha="left",
                 fontweight="bold", fontsize=9)
    fig.text(0.01, -0.02, f"Transmission cost: annuity at {DISCOUNT_RATE:.0%} + FOM over delivered energy "
             f"at {UTILISATION:.0%} utilisation, after availability and losses. Indicative only.",
             fontsize=6.5, color=st.FAINT)
    for ext, kw in (("png", {"dpi": 200}), ("pdf", {})):
        fig.savefig(OUT / f"cost_breakdown.{ext}", bbox_inches="tight", **kw)


if __name__ == "__main__":
    main()
