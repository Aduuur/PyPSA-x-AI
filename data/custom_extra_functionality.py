# SPDX-FileCopyrightText: : 2023- The PyPSA-Eur Authors
#
# SPDX-License-Identifier: MIT

"""
Workshop hook, run after the model is built and before it is solved.

Both changes keep the optimisation problem the same; they only cut the memory
the solve needs, so it fits on laptops with 8 GB:

1. PyPSA writes the limits of every fixed-capacity component as two
   one-variable constraints per snapshot (``<Component>-fix-<attr>-lower/upper``).
   Here they become bounds on the variable itself, which removes about half of
   the rows the solver has to load. The shadow prices of these limits
   (``mu_lower``/``mu_upper`` of fixed components) are no longer reported.
2. The LP file handed to the solver goes next to the results instead of /tmp,
   which on many Linux systems lives in RAM.
"""

from pathlib import Path

import numpy as np
import xarray as xr


def fix_constraints_to_bounds(m):
    """Turn single-variable '-fix-' constraints into variable bounds; return rows moved."""
    moved = 0
    for name in [k for k in m.constraints if "-fix-" in k]:
        comp, rest = name.split("-fix-", 1)
        attr, side = rest.rsplit("-", 1)
        vname = f"{comp}-{attr}"
        d = m.constraints[name].data
        if vname not in m.variables or d.sizes.get("_term", 1) != 1:
            continue  # e.g. lines with losses (p - loss): keep as constraints
        if not bool(((d.coeffs == 1) | (d.labels == -1)).all()):
            continue
        var = m.variables[vname]
        rhs = d.rhs.where(d.labels != -1)  # NaN where the constraint is masked
        if side == "lower":
            cur = var.lower
            rhs = rhs.reindex_like(cur)
            var.lower = xr.where(rhs.isnull(), cur, np.maximum(cur, rhs)).transpose(
                *cur.dims
            )
        else:
            cur = var.upper
            rhs = rhs.reindex_like(cur)
            var.upper = xr.where(rhs.isnull(), cur, np.minimum(cur, rhs)).transpose(
                *cur.dims
            )
        moved += int((d.labels != -1).sum())
        m.remove_constraints(name)
    return moved


def custom_extra_functionality(n, snapshots, snakemake):
    """Keep the memory steps below; add your own constraints after them."""
    m = n.model
    rows = m.constraints.ncons
    moved = fix_constraints_to_bounds(m)
    print(f"Moved {moved:,} of {rows:,} rows to variable bounds", flush=True)

    if snakemake is not None:
        solver_dir = Path(snakemake.output[0]).parent.parent / "solver_tmp"
        solver_dir.mkdir(parents=True, exist_ok=True)
        m._solver_dir = solver_dir

    # Your own constraints go here, e.g. m.add_constraints(...).

    if snakemake is not None:
        add_border_trade_limit(n, snapshots, snakemake)
        add_capacity_path(n, snakemake)


def add_capacity_path(n, snakemake):
    """
    Minimum installed capacity per technology group (e.g. the legal expansion path).

    Config ``capacity_path``: ``enable``, ``groups: {name: [carriers]}``,
    ``min_gw: {name: {horizon: GW}}``. Counts surviving fixed capacity plus new
    builds. A target above the model's potential (surviving capacity plus
    p_nom_max of the extendable ones) is lowered to that potential with a
    warning, so the solve stays feasible.
    """
    cfg = snakemake.config.get("capacity_path", {}) or {}
    if not cfg.get("enable", False):
        return
    horizon = int(snakemake.wildcards.horizon)
    g = n.generators
    ext_all = g.index[g.p_nom_extendable]
    if ext_all.empty:  # e.g. frozen first horizon
        return
    p_nom = n.model["Generator-p_nom"]
    dim = p_nom.dims[0]

    for name, carriers in cfg.get("groups", {}).items():
        targets = {int(k): v for k, v in (cfg.get("min_gw", {}).get(name) or {}).items()}
        if horizon not in targets or targets[horizon] is None:
            continue
        target = float(targets[horizon]) * 1e3
        in_group = g.carrier.isin(carriers)
        ext = g.index[in_group & g.p_nom_extendable]
        fixed = g[in_group & ~g.p_nom_extendable]
        existing = fixed.p_nom[fixed.build_year + fixed.lifetime > horizon].sum()
        potential = existing + g.loc[ext, "p_nom_max"].sum()
        rhs = target - existing
        if target > potential:
            print(
                f"Capacity path {name} {horizon}: target {target / 1e3:.1f} GW above "
                f"model potential {potential / 1e3:.1f} GW, lowered to the potential",
                flush=True,
            )
            rhs = potential - existing
        if rhs <= 0 or ext.empty:
            print(
                f"Capacity path {name} {horizon}: met by existing "
                f"{existing / 1e3:.1f} GW (target {target / 1e3:.1f} GW)",
                flush=True,
            )
            continue
        n.model.add_constraints(
            p_nom.sel({dim: ext}).sum() >= rhs, name=f"capacity_path_{name}"
        )
        print(
            f"Capacity path {name} {horizon}: >= {target / 1e3:.1f} GW "
            f"({existing / 1e3:.1f} GW existing, >= {rhs / 1e3:.1f} GW new)",
            flush=True,
        )


def add_border_trade_limit(n, snapshots, snakemake):
    """
    Optional cap on annual net imports over all borders (scripts/add_border_trade.py).

    Config: border_trade.net_import_limit, in TWh per year, either one number
    or {horizon: number}; empty or null means no limit. Negative values force
    net exports.
    """
    cfg = snakemake.config.get("border_trade", {}) or {}
    limit = cfg.get("net_import_limit")
    if not cfg.get("enable", False) or limit in (None, {}, ""):
        return
    if isinstance(limit, dict):
        limit = {int(k): v for k, v in limit.items()}.get(int(snakemake.wildcards.horizon))
        if limit is None:
            return

    gens = n.generators.index[n.generators.carrier.str.startswith("border trade")]
    if gens.empty:
        return
    w = n.snapshot_weightings.generators.loc[snapshots]
    nyears = w.sum() / 8760.0
    p = n.model["Generator-p"].loc[snapshots, gens]
    lhs = (p * xr.DataArray(w.values, coords={"snapshot": snapshots})).sum()
    n.model.add_constraints(
        lhs <= float(limit) * 1e6 * nyears, name="border_trade_net_import_limit"
    )
    print(f"Border trade: net imports limited to {limit} TWh/a", flush=True)
