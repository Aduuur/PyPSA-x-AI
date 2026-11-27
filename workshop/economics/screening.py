# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Screening of the cable before it is in the model: what does a MWh delivered
to Germany cost, and what is it worth there?

Builds on the other roles' results, read at runtime:

- role 1: cable cost, losses and availability per route case and level
  (low / central / high) from ``workshop/cable/cable_parameters.yaml``
  (``workshop/cable/cable_cost.py``) and the German node (``DE0 7AC``);
- role 2: hourly onshore wind capacity factor for Rio Grande do Norte
  (``resources/brazil/rn_onwind_cf_2013_utc.csv``, from
  ``workshop/brazil/build_rn_onwind_profile.py``);
- solved runs: the hourly price at the German node in each horizon.

Everything is per MW of cable, so no cable size is assumed. The wind farm is
sized as a multiple of the cable (``--oversize``); output above the available
cable rating (rating x availability) is curtailed. Cable and converter costs,
end-to-end efficiency and availability are role 1's. Wind costs are the
public PyPSA-Eur ``onwind`` entry of each horizon, a placeholder until role 2
delivers Brazilian costs.

Two financing variants:

- ``public``: the model's default discount rate for every asset, no interest
  during construction. Written to ``results/economics/screening/``.
- ``project``: cost of capital and interest during construction per asset from
  ``financing.py`` (read at runtime from the confidential term sheet). Derived
  from confidential data, so it is written to ``workshop/private/`` only and
  never printed.

Value is the price at the German node in a run *without* the cable, weighted
with the delivered energy. It ignores that the cable itself lowers prices
there (cannibalisation): an upper bound on the value, to be replaced by the
model run with the cable.

    pixi run python workshop/economics/screening.py
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workshop" / "plotstyle"))
sys.path.insert(0, str(ROOT / "workshop" / "economics"))
import studystyle as st  # noqa: E402
from financing import annuity  # noqa: E402

CABLE = ROOT / "workshop" / "cable" / "cable_parameters.yaml"
REF_CASE = "reference"
PROFILE = ROOT / "resources" / "brazil" / "rn_onwind_cf_2013_utc.csv"
NODE = "DE0 7AC"  # role 1, agreed in the group
OUT_PUBLIC = ROOT / "results" / "economics" / "screening"
OUT_PRIVATE = ROOT / "workshop" / "private" / "screening"


def load_cable():
    """Role 1's parameters: {(case, level): dict(investment, FOM, lifetime, efficiency, p_max_pu)}."""
    import yaml

    p = yaml.safe_load(open(CABLE))
    out = {}
    for level, v in p["levels"].items():
        out[(REF_CASE, level)] = dict(v, length_km=p["length_km"])
    # other routes: role 1 gives the investment only; FOM, lifetime, losses and
    # availability are taken from the reference route at the same level
    for case, levels in p.get("route_alternatives_investment_EUR_per_MW", {}).items():
        for level, inv in levels.items():
            out[(case, level)] = dict(p["levels"][level], investment_EUR_per_MW=inv,
                                      length_km=float("nan"))
    return out, p


def load_profile(snapshots):
    """Role 2's hourly profile averaged onto the model's snapshots."""
    cf = pd.read_csv(PROFILE, index_col="timestamp_utc", parse_dates=True)["rn_onwind_cf"]
    cf.index = cf.index.tz_localize(None)
    step = snapshots[1] - snapshots[0]
    cf = cf.resample(step).mean().reindex(snapshots)
    if cf.isna().any():
        raise ValueError("profile does not cover the model snapshots")
    return cf


def annual_cost(c, tech, rate, idc):
    """EUR per MW and year: investment x IDC x (annuity + FOM)."""
    row = c.loc[tech]
    return row.investment * idc * (annuity(rate, row.lifetime) + row.FOM / 100)


def screen(n, costs, cf, cable, oversize, rates):
    """Per MW of cable, for one horizon. rates: {asset: (rate, idc)}."""
    w = n.snapshot_weightings.generators
    price = n.buses_t.marginal_price[NODE]
    eta = cable["efficiency"]
    sent = np.minimum(cf * oversize, cable["p_max_pu"])  # MW per MW of cable
    delivered = sent * eta
    e_wind = (cf * oversize * w).sum()
    e_del = (delivered * w).sum()

    r_c, idc_c = rates["cable"]
    r_b, idc_b = rates["brazil"]
    cable_cost = cable["investment_EUR_per_MW"] * idc_c * (
        annuity(r_c, cable["lifetime_a"]) + cable["FOM_pct_per_a"] / 100)
    cost = {
        "cable": cable_cost,
        "wind": annual_cost(costs, "onwind", r_b, idc_b) * oversize
        + costs.at["onwind", "VOM"] * e_wind,
    }
    total = sum(cost.values())
    value = (delivered * price * w).sum()
    return {
        "length_km": cable["length_km"],
        "efficiency": eta,
        "availability": cable["p_max_pu"],
        "cable_utilisation": (sent * w).sum() / w.sum(),
        "curtailment_share": 1 - (sent * w).sum() / e_wind,
        "delivered_MWh_per_MW": e_del,
        **{f"cost_{k}_EUR_MWh": v / e_del for k, v in cost.items()},
        "cost_EUR_MWh": total / e_del,
        "value_EUR_MWh": value / e_del,
        "price_avg_EUR_MWh": (price * w).sum() / w.sum(),
        "margin_EUR_MWh": (value - total) / e_del,
        # share of role 1's cable cost at which the delivered energy pays for itself
        "breakeven_cable_cost_share": max((value - cost["wind"]) / cost["cable"], 0),
    }


def run(args, variant, rates_fn):
    cables, _ = load_cable()
    rows = []
    for run_name in args.runs:
        for f in sorted((ROOT / "results" / run_name / "networks").glob("solved_*.nc")):
            year = int(f.stem.split("_")[1])
            if year < args.from_year:
                continue
            n = pypsa.Network(f)
            cf = load_profile(n.snapshots)
            costs = pd.read_csv(ROOT / "resources" / run_name / f"costs_{year}_processed.csv",
                                index_col=0)
            rates = rates_fn(costs)
            for (case, level), cable in cables.items():
                for ov in args.oversize:
                    rows.append({"variant": variant, "run": run_name, "year": year,
                                 "case": case, "level": level, "oversize": ov,
                                 **screen(n, costs, cf, cable, ov, rates)})
    return pd.DataFrame(rows)


def figure(df, out, title_suffix):
    """Cost stack against value at the German node: reference route, one panel
    per level of role 1's cable cost (low / central / high)."""
    import matplotlib.pyplot as plt

    st.use()
    ref = df[(df.case == REF_CASE) & (df.oversize == df.oversize.min())]
    runs = list(ref.run.unique())
    levels = [lv for lv in ("low", "central", "high") if lv in set(ref.level)]
    fig, axes = plt.subplots(1, len(levels), figsize=(9.6, 3.4), sharey=True, squeeze=False)
    for ax, level in zip(axes[0], levels):
        d = ref[(ref.level == level) & (ref.run == runs[0])].set_index("year")
        x = list(range(len(d)))
        parts = pd.DataFrame({"Onshore wind": d.cost_wind_EUR_MWh,
                              "Brazil cable": d.cost_cable_EUR_MWh})
        st.stacked_bars(ax, x, parts)
        for r, colour in zip(runs, [st.TEXT, st.BLUE, st.GREEN]):
            v = ref[(ref.run == r) & (ref.level == level)].set_index("year").value_EUR_MWh
            st.line(ax, x, v.reindex(d.index).values, colour,
                    label=r if level == levels[-1] else None)
        ax.set_xticks(x, d.index)
        ax.set_title(f"cable cost: {level} (role 1)", loc="left", fontsize=9)
    st.legend_squares(axes[0][0], [(st.GROUPS["Onshore wind"], "Wind in Brazil"),
                                   (st.GROUPS["Brazil cable"], "Cable incl. converters"),
                                   (st.TEXT, "Value in Germany (lines)")], fontsize=7.5)
    fig.suptitle(f"Cost of a MWh delivered to Wilhelmshaven against its value, EUR/MWh{title_suffix}",
                 x=0.01, ha="left", fontweight="bold")
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / "screening.pdf")
    fig.savefig(out / "screening.png", dpi=300)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", nargs="+", default=["de10-myopic", "cap2050-relaxed"])
    p.add_argument("--from-year", type=int, default=2035, help="first horizon the cable can run")
    p.add_argument("--oversize", nargs="+", type=float, default=[1.0, 1.5],
                   help="MW of wind per MW of cable")
    p.add_argument("--no-project", action="store_true", help="skip the project-finance variant")
    a = p.parse_args()
    a.runs = [r for r in a.runs if (ROOT / "results" / r / "networks").is_dir()]

    for f, who in [(CABLE, "role 1: workshop/cable/cable_cost.py"),
                   (PROFILE, "role 2: workshop/brazil/build_rn_onwind_profile.py")]:
        if not f.is_file():
            sys.exit(f"{f.relative_to(ROOT)} missing; build it first ({who})")

    # public: the model's own default rate per technology, no IDC
    def public_rates(costs):
        r = costs.at["onwind", "discount rate"]  # harmonised default, also role 1's
        return {"cable": (r, 1.0), "brazil": (r, 1.0)}

    pub = run(a, "public", public_rates)
    OUT_PUBLIC.mkdir(parents=True, exist_ok=True)
    pub.to_csv(OUT_PUBLIC / "screening_public.csv", index=False)
    figure(pub, OUT_PUBLIC, " (public cost of capital)")

    cols = ["cost_wind_EUR_MWh", "cost_cable_EUR_MWh", "cost_EUR_MWh", "value_EUR_MWh",
            "margin_EUR_MWh", "breakeven_cable_cost_share", "cable_utilisation"]
    view = pub[(pub.case == REF_CASE) & (pub.oversize == 1.0)]
    with pd.option_context("display.width", 200, "display.float_format", "{:,.2f}".format):
        print("Reference route, wind = cable rating, public cost of capital:")
        print(view.set_index(["run", "year", "level"])[cols])
    print(f"\nwritten {OUT_PUBLIC.relative_to(ROOT)}/")

    if not a.no_project:
        from financing import TERM_SHEET, load

        if not TERM_SHEET.is_file():
            print("term sheet not in this workspace: project-finance variant skipped")
            return
        fin = load()

        def project_rates(costs):
            return {k: (fin[k]["wacc"], fin[k]["idc_factor"]) for k in ("cable", "brazil")}

        prj = run(a, "project", project_rates)
        OUT_PRIVATE.mkdir(parents=True, exist_ok=True)
        prj.to_csv(OUT_PRIVATE / "screening_project.csv", index=False)
        figure(prj, OUT_PRIVATE, " (project finance, CONFIDENTIAL)")
        print(f"written {OUT_PRIVATE.relative_to(ROOT)}/ (derived from confidential data: local only)")


if __name__ == "__main__":
    main()
