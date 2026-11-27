# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Role 4 results pipeline: one evaluation over all solved runs.

Reads every ``results/<run>/networks/solved_<year>.nc``, computes the same
metrics for each run and horizon, compares each run with a reference run and
writes tables and figures to ``results/economics/`` (git-ignored).

    pixi run python workshop/economics/analyse_runs.py
    pixi run python workshop/economics/analyse_runs.py --reference de10-myopic \
        --runs de10-myopic cable --discount-rate 0.02 --window 2035 2045

Metrics per run and horizon
    system cost (capex, opex) by technology group, demand, load-weighted and
    peak price, emissions, price of the CO2 cap, generation and capacity by
    group, flow over the Brazil cable, and who pays and who earns: consumers
    (demand x local price), producers by group (revenue minus cost), grid
    (congestion rent), Brazil cable.

Present value
    Each horizon stands for the years until the next one (the last for
    ``--last-years``), discounted to the first horizon at ``--discount-rate``.
    The total is reported for all horizons and for ``--window`` separately,
    so the result can be read with and without 2050.

Everything here uses whole-model results only and reads no file from
``workshop/inputs/``.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import pypsa

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "workshop" / "plotstyle"))
import studystyle as st  # noqa: E402


def is_brazil(name):
    return "brazil" in str(name).lower()


# ---------------------------------------------------------------- metrics


def annual(n, df):
    """Weighted sum over snapshots of a time series DataFrame."""
    return df.mul(n.snapshot_weightings.generators, axis=0).sum()


def emissions(n):
    """CO2 from generators and links (fuel input x carrier intensity), Mt."""
    co2 = n.carriers.co2_emissions
    total = 0.0
    g = n.generators
    if len(g):
        e = annual(n, n.generators_t.p) / g.efficiency * g.carrier.map(co2).fillna(0)
        total += e.sum()
    links = n.links
    if len(links):
        fuel = links.bus0.map(n.buses.carrier).map(co2).fillna(0)
        total += (annual(n, n.links_t.p0) * fuel).sum()
    return total / 1e6


def cap_price(n):
    gc = n.global_constraints
    rows = gc[gc.index.str.contains("CO2", case=False)]
    return -rows.mu.sum() if len(rows) else float("nan")


def ac_buses(n):
    """AC buses of the system under study (Germany), excluding Brazil."""
    b = n.buses
    return b.index[(b.carrier == "AC") & ~b.index.map(is_brazil) & (b.country != "BR")]


def prices_and_demand(n):
    buses = ac_buses(n)
    loads = n.loads[n.loads.bus.isin(buses)]
    p = n.loads_t.p.reindex(columns=loads.index).fillna(0)
    lmp = n.buses_t.marginal_price[loads.bus].set_axis(loads.index, axis=1)
    demand = annual(n, p).sum()
    payment = annual(n, p * lmp).sum()
    return {
        "demand_TWh": demand / 1e6,
        "consumer_cost_bnEUR": payment / 1e9,
        "price_avg_EUR_MWh": payment / demand if demand else float("nan"),
        "price_peak_EUR_MWh": n.buses_t.marginal_price[buses].max().max(),
        "price_zero_share": (n.buses_t.marginal_price[buses].mean(axis=1) < 0.1).mean(),
    }


GRID = "Grid (AC/DC)"  # not a technology group: st.color() maps it to "Other"


def by_group_series(s, grid=False):
    """Sum a statistics Series indexed (component, carrier) into technology groups.
    st.by_group drops AC/DC lines; with grid=True they are kept as one extra entry."""
    s = s.groupby(level="carrier").sum() if isinstance(s.index, pd.MultiIndex) else s
    out = st.by_group(s)
    if grid:
        out[GRID] = s.reindex(list(st.TRANSMISSION)).fillna(0).sum()
    return out


def group_costs(n):
    s = n.statistics
    capex = by_group_series(s.capex(), grid=True) / 1e9
    opex = by_group_series(s.opex(), grid=True) / 1e9
    return capex, opex


def group_surplus(n):
    """Revenue minus cost by technology group, billion EUR. Excludes loads."""
    s = n.statistics
    rev = s.revenue(aggregate_across_components=False)
    rev = rev.drop("Load", level="component", errors="ignore")
    cost = s.capex().add(s.opex(), fill_value=0)
    surplus = rev.groupby(level="carrier").sum().sub(
        cost.groupby(level="carrier").sum(), fill_value=0
    )
    grid = surplus.reindex(["AC", "DC"]).fillna(0).sum()
    producers = st.by_group(surplus) / 1e9
    return producers, grid / 1e9


def brazil_cable(n):
    """Flow, utilisation and congestion rent of links whose name or carrier says Brazil."""
    links = n.links[n.links.index.map(is_brazil) | n.links.carrier.map(is_brazil)]
    if links.empty:
        return {"cable_GW": 0.0, "cable_flow_TWh": 0.0, "cable_utilisation": float("nan"),
                "cable_rent_bnEUR": 0.0}
    p0 = n.links_t.p0[links.index]
    p1 = n.links_t.p1[links.index]
    lmp = n.buses_t.marginal_price
    # flow delivered to the side that is not Brazil, whichever end that is
    to_de = links.bus1.map(lambda b: not is_brazil(b) and n.buses.at[b, "country"] != "BR")
    delivered = pd.concat(
        [-p1[c] if to_de[c] else -p0[c] for c in links.index], axis=1
    )
    rent = -(p0 * lmp[links.bus0].values + p1 * lmp[links.bus1].values)
    cap = (links.p_nom_opt * links.p_max_pu.abs()).sum()
    flow = annual(n, delivered).sum()
    hours = n.snapshot_weightings.generators.sum()
    return {
        "cable_GW": links.p_nom_opt.sum() / 1e3,
        "cable_flow_TWh": flow / 1e6,
        "cable_utilisation": flow / (cap * hours) if cap else float("nan"),
        "cable_rent_bnEUR": annual(n, rent).sum() / 1e9,
    }


def analyse_network(n):
    capex, opex = group_costs(n)
    producers, grid = group_surplus(n)
    s = n.statistics
    gen = by_group_series(s.supply(bus_carrier="AC", comps=["Generator", "StorageUnit", "Link"]))
    gen = gen.drop("Storage", errors="ignore") / 1e6
    capacity = by_group_series(s.optimal_capacity(comps=["Generator", "StorageUnit", "Link"],
                                                  bus_carrier="AC")) / 1e3
    scalars = {
        "system_cost_bnEUR": capex.sum() + opex.sum(),
        "capex_bnEUR": capex.sum(),
        "opex_bnEUR": opex.sum(),
        "co2_Mt": emissions(n),
        "co2_cap_price_EUR_t": cap_price(n),
        "grid_rent_bnEUR": grid,
        **prices_and_demand(n),
        **brazil_cable(n),
    }
    tables = {
        "cost_capex_bnEUR": capex,
        "cost_opex_bnEUR": opex,
        "generation_TWh": gen,
        "capacity_GW": capacity,
        "producer_surplus_bnEUR": producers,
    }
    return scalars, tables


def find_runs(results):
    runs = {}
    for f in sorted(results.glob("*/networks/solved_*.nc")):
        m = re.fullmatch(r"solved_(\d{4})\.nc", f.name)
        if m:
            runs.setdefault(f.parents[1].name, {})[int(m.group(1))] = f
    return runs


def analyse_runs(runs):
    scalars, tables = [], {}
    for run, files in runs.items():
        for year, f in sorted(files.items()):
            print(f"  {run} {year}", file=sys.stderr)
            n = pypsa.Network(f)
            sc, tb = analyse_network(n)
            scalars.append({"run": run, "year": year, **sc})
            for name, s in tb.items():
                tables.setdefault(name, []).append(s.rename((run, year)))
    scalars = pd.DataFrame(scalars).set_index(["run", "year"]).sort_index()
    tables = {
        k: pd.concat(v, axis=1).T.rename_axis(["run", "year"]).fillna(0).sort_index()
        for k, v in tables.items()
    }
    return scalars, tables


# ---------------------------------------------------------- present value


def year_weights(years, rate, last_years):
    """Discounted number of years each horizon stands for, base = first horizon."""
    years = sorted(years)
    base = years[0]
    w = {}
    for i, y in enumerate(years):
        span = (years[i + 1] - y) if i + 1 < len(years) else last_years
        w[y] = sum(1 / (1 + rate) ** (t - base) for t in range(y, y + span))
    return pd.Series(w)


def present_values(scalars, rate, last_years, window):
    cols = ["system_cost_bnEUR", "capex_bnEUR", "opex_bnEUR", "consumer_cost_bnEUR",
            "grid_rent_bnEUR", "cable_rent_bnEUR"]
    out = {}
    for run, df in scalars.groupby(level="run"):
        df = df.droplevel("run")
        w = year_weights(df.index, rate, last_years)
        lo, hi = window
        inside = w.index[(w.index >= lo) & (w.index <= hi)]
        row = {f"{c}_PV_all": (df[c] * w).sum() for c in cols}
        row |= {f"{c}_PV_{lo}-{hi}": (df.loc[inside, c] * w[inside]).sum() for c in cols}
        row["co2_Mt_cumulative"] = (df["co2_Mt"] * year_weights(df.index, 0, last_years)).sum()
        out[run] = row
    return pd.DataFrame(out).T.rename_axis("run")


def compare(scalars, tables, pv, reference):
    if reference not in scalars.index.get_level_values("run"):
        return None, None, None
    ref = scalars.xs(reference, level="run")
    d_scalars = scalars.groupby(level="run", group_keys=True).apply(
        lambda df: df.droplevel("run") - ref.reindex(df.droplevel("run").index)
    )
    d_pv = pv - pv.loc[reference]
    surplus = tables["producer_surplus_bnEUR"]
    ref_s = surplus.xs(reference, level="run")
    d_surplus = surplus.groupby(level="run", group_keys=True).apply(
        lambda df: df.droplevel("run").sub(ref_s.reindex(df.droplevel("run").index), fill_value=0)
    )
    return d_scalars, d_pv, d_surplus


# ----------------------------------------------------------------- figures


def fig_cost(tables, run, out):
    import matplotlib.pyplot as plt

    cost = tables["cost_capex_bnEUR"].add(tables["cost_opex_bnEUR"], fill_value=0).xs(run, level="run")
    cost = cost[[g for g in [*st.GROUPS, GRID] if g in cost.columns and cost[g].abs().sum() > 0.01]]
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    st.stacked_bars(ax, range(len(cost)), cost.clip(lower=0))
    ax.set_xticks(range(len(cost)), cost.index)
    ax.set_title(f"Annual system cost in Germany by technology, billion EUR ({run})", loc="left")
    st.legend_squares(ax, [(st.color(g), g) for g in reversed(cost.columns)],
                      loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=7.5)
    save(fig, out / f"system_cost_{run}")


def fig_generation(tables, run, out):
    import matplotlib.pyplot as plt

    gen = tables["generation_TWh"].xs(run, level="run")
    gen = gen[[g for g in st.GROUPS if g in gen.columns and gen[g].sum() > 0.5]]
    fig, ax = plt.subplots(figsize=(5.6, 3.4))
    st.stacked_bars(ax, range(len(gen)), gen)
    ax.set_xticks(range(len(gen)), gen.index)
    ax.set_title(f"Electricity generation in Germany, TWh ({run})", loc="left")
    st.legend_squares(ax, [(st.GROUPS[g], g) for g in reversed(gen.columns)],
                      loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=7.5)
    save(fig, out / f"generation_{run}")


def fig_price_co2(scalars, reference, out):
    """Average price, CO2 emissions and price of the cap, one line per run."""
    import matplotlib.pyplot as plt

    panels = [("price_avg_EUR_MWh", "Average electricity price, EUR/MWh"),
              ("co2_Mt", "CO2 emissions, Mt"),
              ("co2_cap_price_EUR_t", "Price of the CO2 cap, EUR/t (log)")]
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 3.2))
    runs = list(scalars.index.unique("run"))
    others = [r for r in runs if r != reference]
    colours = {reference: st.NEUTRAL}
    palette = [st.VERMILLION, st.BLUE, st.GREEN, st.ORANGE, st.PINK, st.SKY]
    colours |= {r: palette[i % len(palette)] for i, r in enumerate(others)}
    for ax, (col, title) in zip(axes, panels):
        for r in [reference, *others] if reference in runs else runs:
            df = scalars.xs(r, level="run")[col]
            if col == "co2_cap_price_EUR_t":
                df = df.clip(lower=1)
            st.line(ax, df.index, df.values, colours[r], label=r if len(runs) > 1 else None,
                    values=len(runs) == 1 and col != "co2_cap_price_EUR_t")
        if col == "co2_cap_price_EUR_t":
            ax.set_yscale("log")
        ax.set_title(title, loc="left", fontsize=9)
        ax.set_xticks(sorted(scalars.index.unique("year")))
    fig.suptitle("Germany: prices and emissions by horizon", x=0.01, ha="left", fontweight="bold")
    save(fig, out / "price_co2")


def fig_delta(d_scalars, d_surplus, reference, out):
    """For each run against the reference: change in system cost and who gains or loses."""
    import matplotlib.pyplot as plt

    for run in d_scalars.index.unique("run"):
        if run == reference:
            continue
        ds = d_scalars.xs(run, level="run")
        parts = pd.DataFrame({
            "Consumers": -ds["consumer_cost_bnEUR"],
            "Grid": ds["grid_rent_bnEUR"],
            "Brazil cable": ds["cable_rent_bnEUR"],
        })
        producers = d_surplus.xs(run, level="run").sum(axis=1).reindex(parts.index).fillna(0)
        parts.insert(1, "Producers", producers)
        colours = {"Consumers": st.BLUE, "Producers": st.NEUTRAL, "Grid": "#555555",
                   "Brazil cable": st.VERMILLION}
        fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.4))
        st.bars(axes[0], range(len(ds)), -ds["system_cost_bnEUR"].values,
                color=st.VERMILLION, fmt="{:,.1f}")
        axes[0].set_xticks(range(len(ds)), ds.index)
        axes[0].axhline(0, color=st.TEXT, lw=0.8)
        axes[0].set_title("System cost saved, billion EUR a year", loc="left", fontsize=9)
        x = range(len(parts))
        width = 0.8 / len(parts.columns)
        for i, c in enumerate(parts.columns):
            axes[1].bar([xi - 0.4 + width * (i + 0.5) for xi in x], parts[c], width=width,
                        color=colours[c], linewidth=0, zorder=2)
        axes[1].set_xticks(list(x), parts.index)
        axes[1].axhline(0, color=st.TEXT, lw=0.8)
        axes[1].set_title("Who gains (+) and who loses (-), billion EUR a year", loc="left", fontsize=9)
        st.legend_squares(axes[1], [(colours[c], c) for c in parts.columns], fontsize=7.5)
        fig.suptitle(f"{run} against {reference}", x=0.01, ha="left", fontweight="bold")
        save(fig, out / f"delta_{run}")


def save(fig, path):
    import matplotlib.pyplot as plt

    fig.savefig(path.with_suffix(".pdf"))
    fig.savefig(path.with_suffix(".png"), dpi=300)
    plt.close(fig)


# -------------------------------------------------------------------- main


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--results", default=ROOT / "results", type=Path)
    p.add_argument("--out", default=ROOT / "results" / "economics", type=Path)
    p.add_argument("--runs", nargs="*", help="run names (default: all solved runs)")
    p.add_argument("--reference", default="de10-myopic", help="run without the cable")
    p.add_argument("--discount-rate", default=0.02, type=float,
                   help="social discount rate for present values (config default 0.02)")
    p.add_argument("--last-years", default=5, type=int, help="years the last horizon stands for")
    p.add_argument("--window", nargs=2, type=int, default=[2035, 2045],
                   help="horizons of the headline result, e.g. without 2050")
    p.add_argument("--no-figures", action="store_true")
    a = p.parse_args()

    runs = find_runs(a.results)
    if a.runs:
        runs = {r: runs[r] for r in a.runs if r in runs}
    if not runs:
        sys.exit(f"no solved runs found under {a.results}")
    a.out.mkdir(parents=True, exist_ok=True)
    print(f"Analysing {len(runs)} run(s): {', '.join(runs)}", file=sys.stderr)

    scalars, tables = analyse_runs(runs)
    pv = present_values(scalars, a.discount_rate, a.last_years, a.window)
    d_scalars, d_pv, d_surplus = compare(scalars, tables, pv, a.reference)

    scalars.to_csv(a.out / "metrics.csv")
    pv.to_csv(a.out / "present_values.csv")
    for name, df in tables.items():
        df.to_csv(a.out / f"{name}.csv")
    if d_scalars is not None:
        d_scalars.to_csv(a.out / f"delta_metrics_vs_{a.reference}.csv")
        d_pv.to_csv(a.out / f"delta_present_values_vs_{a.reference}.csv")
        d_surplus.to_csv(a.out / f"delta_producer_surplus_vs_{a.reference}.csv")

    if not a.no_figures:
        st.use()
        for run in runs:
            fig_cost(tables, run, a.out)
            fig_generation(tables, run, a.out)
        fig_price_co2(scalars, a.reference, a.out)
        if d_scalars is not None:
            fig_delta(d_scalars, d_surplus, a.reference, a.out)

    with pd.option_context("display.width", 160, "display.max_columns", 20,
                           "display.float_format", "{:,.2f}".format):
        print(scalars[["system_cost_bnEUR", "demand_TWh", "price_avg_EUR_MWh",
                       "price_peak_EUR_MWh", "co2_Mt", "co2_cap_price_EUR_t", "cable_flow_TWh"]])
        print(f"\nPresent values (rate {a.discount_rate:.1%}, base {scalars.index.unique('year').min()}),"
              " billion EUR")
        print(pv.filter(like="system_cost").join(pv.filter(like="consumer_cost")))
        if d_pv is not None and len(d_pv) > 1:
            print(f"\nChange against {a.reference}")
            print(d_pv.drop(a.reference).filter(like="_PV_"))
    print(f"\nWritten to {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
