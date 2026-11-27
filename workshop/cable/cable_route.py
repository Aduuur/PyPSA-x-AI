# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Candidate routes for the Brazil-Germany HVDC cable from GEBCO_2025 bathymetry.

Least-cost paths over the sea on a coarsened grid (Dijkstra, 8 neighbours),
for every pair of candidate landing points and two route variants:

- ``shortest``: weight = great-circle distance; only land is excluded.
- ``shallow``:  distance weighted up with depth beyond the qualified depth,
  so the route seeks shallower water where it can (in practice: it crosses
  the equatorial Atlantic towards West Africa and follows the African and
  Iberian continental margin north).

Each route is computed via the English Channel and, separately, around
Scotland (Dover Strait blocked), since the Channel is among the busiest
shipping lanes in the world.

Uses public data only (GEBCO_2025, public-domain; landing points are public
coastal towns). Outputs go to ``results/cable/`` (git-ignored):
``routes.csv`` (summary), ``routes.gpkg`` (lines), ``profiles.csv`` and two
figures.

Run from the repo root:

    pixi run python workshop/cable/cable_route.py
"""

import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import xarray as xr
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from shapely.geometry import LineString

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "workshop/plotstyle").is_dir())
sys.path.insert(0, str(ROOT / "workshop/plotstyle"))
import studystyle as st  # noqa: E402

BATHY = ROOT / "data-brazil/bathymetry_atlantic/gebco_2025_atlantic_30s.nc"
OUT = ROOT / "results/cable"

COARSEN = 6  # 30" -> 3' (0.05 deg) routing grid
R_EARTH = 6371.0  # km

# Reference depths (m) from the role brief: deepest laid / deepest qualified.
DEPTH_LAID = 2150
DEPTH_QUALIFIED = 3000
DEPTH_PENALTY = 1.0  # extra weight per 1000 m beyond DEPTH_QUALIFIED in "shallow"

# Candidate landing points (public coastal towns, lat, lon). Brazil: north-east
# coast, where existing transatlantic telecom cables land. Agreed with Role 2:
# Natal region. The others stay in for comparison.
BR_AGREED = "Natal (RN)"
LANDING_BR = {
    "Fortaleza/Pecem (CE)": (-3.55, -38.81),
    "Natal (RN)": (-5.78, -35.20),
    "Sao Luis (MA)": (-2.53, -44.30),
}
# Germany: North Sea coast, near existing HVDC landfalls; node to be agreed with Role 3.
LANDING_DE = {
    "Wilhelmshaven": (53.52, 8.13),
    "Buesum": (54.13, 8.86),
}
# Box closed to force the route around Scotland (Dover Strait).
DOVER_BOX = dict(lat=(50.6, 51.4), lon=(0.9, 2.1))


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def load_grid():
    da = xr.open_dataset(BATHY).elevation
    fine = da
    # max over the block: a cell counts as sea only if all of it is sea
    coarse = da.coarsen(lat=COARSEN, lon=COARSEN, boundary="trim").max()
    return fine, coarse


def build_graph(lat, lon, elev, variant, block_dover):
    ny, nx = elev.shape
    sea = elev < 0
    if block_dover:
        la = (lat >= DOVER_BOX["lat"][0]) & (lat <= DOVER_BOX["lat"][1])
        lo = (lon >= DOVER_BOX["lon"][0]) & (lon <= DOVER_BOX["lon"][1])
        sea = sea & ~(la[:, None] & lo[None, :])
    depth = np.where(sea, -elev, 0).astype(float)
    if variant == "shallow":
        factor = 1 + DEPTH_PENALTY * np.clip(depth - DEPTH_QUALIFIED, 0, None) / 1000
    else:
        factor = np.ones_like(depth)
    idx = np.arange(ny * nx).reshape(ny, nx)
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    rows, cols, w = [], [], []
    for dy, dx in [(0, 1), (1, 0), (1, 1), (1, -1)]:
        ys = slice(max(0, -dy), ny - max(0, dy))
        xs = slice(max(0, -dx), nx - max(0, dx))
        yt = slice(ys.start + dy, ys.stop + dy)
        xt = slice(xs.start + dx, xs.stop + dx)
        ok = sea[ys, xs] & sea[yt, xt]
        d = haversine(LAT[ys, xs], LON[ys, xs], LAT[yt, xt], LON[yt, xt])
        f = 0.5 * (factor[ys, xs] + factor[yt, xt])
        rows.append(idx[ys, xs][ok])
        cols.append(idx[yt, xt][ok])
        w.append((d * f)[ok])
    r, c, w = np.concatenate(rows), np.concatenate(cols), np.concatenate(w)
    g = coo_matrix((np.r_[w, w], (np.r_[r, c], np.r_[c, r])), shape=(ny * nx, ny * nx)).tocsr()
    return g, sea


def nearest_sea(lat, lon, sea, plat, plon):
    LAT, LON = np.meshgrid(lat, lon, indexing="ij")
    d = np.where(sea, haversine(plat, plon, LAT, LON), np.inf)
    i = np.unravel_index(np.argmin(d), d.shape)
    return i, d[i]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fine, coarse = load_grid()
    lat, lon = coarse.lat.values, coarse.lon.values
    elev = coarse.values.astype(float)
    nx = len(lon)

    rows, lines, profiles = [], [], []
    for corridor, block in [("Channel", False), ("Scotland", True)]:
        for variant in ["shortest", "shallow"]:
            g, sea = build_graph(lat, lon, elev, variant, block)
            for de_name, (dla, dlo) in LANDING_DE.items():
                (iy, ix), shore_de = nearest_sea(lat, lon, sea, dla, dlo)
                src = iy * nx + ix
                dist, pred = dijkstra(g, indices=src, return_predecessors=True)
                for br_name, (bla, blo) in LANDING_BR.items():
                    (jy, jx), shore_br = nearest_sea(lat, lon, sea, bla, blo)
                    node = jy * nx + jx
                    if not np.isfinite(dist[node]):
                        continue
                    path = [node]
                    while path[-1] != src:
                        path.append(pred[path[-1]])
                    py, px = np.divmod(np.array(path), nx)
                    plat = np.r_[bla, lat[py], dla]
                    plon = np.r_[blo, lon[px], dlo]
                    seg = haversine(plat[:-1], plon[:-1], plat[1:], plon[1:])
                    km = np.r_[0, np.cumsum(seg)]
                    # depth along the route from the 30" grid, sampled every ~2 km
                    s = np.arange(0, km[-1], 2.0)
                    slat, slon = np.interp(s, km, plat), np.interp(s, km, plon)
                    z = fine.interp(lat=("p", slat), lon=("p", slon), method="nearest").values
                    depth = np.clip(-z, 0, None)
                    step = np.diff(np.r_[s, km[-1]])
                    name = f"{br_name} - {de_name}, {corridor}, {variant}"
                    rows.append(dict(
                        route=name, brazil=br_name, germany=de_name, corridor=corridor,
                        variant=variant, length_km=km[-1],
                        great_circle_km=haversine(bla, blo, dla, dlo),
                        max_depth_m=depth.max(), mean_depth_m=depth.mean(),
                        km_deeper_2150m=step[depth > DEPTH_LAID].sum(),
                        km_deeper_3000m=step[depth > DEPTH_QUALIFIED].sum(),
                        km_deeper_4000m=step[depth > 4000].sum(),
                        km_deeper_5000m=step[depth > 5000].sum(),
                        km_shallower_200m=step[depth <= 200].sum(),
                        shore_offset_km=shore_br + shore_de,
                    ))
                    lines.append(dict(route=name, geometry=LineString(zip(plon, plat))))
                    profiles.append(pd.DataFrame(dict(route=name, km=s, depth_m=depth)))

    df = pd.DataFrame(rows).round(0)
    df.to_csv(OUT / "routes.csv", index=False)
    gpd.GeoDataFrame(lines, crs="EPSG:4326").to_file(OUT / "routes.gpkg")
    prof = pd.concat(profiles)
    prof.to_csv(OUT / "profiles.csv", index=False)
    pd.set_option("display.width", 250)
    print(df.drop(columns=["route"]).to_string(index=False))
    plot(fine, gpd.read_file(OUT / "routes.gpkg"), prof, df)


def plot(fine, routes, prof, df):
    st.use()
    # map
    sub = fine.coarsen(lat=8, lon=8, boundary="trim").mean()
    fig = plt.figure(figsize=(5.6, 6.2), layout="none")
    ax = fig.add_axes([0.02, 0.12, 0.96, 0.82])
    cax = fig.add_axes([0.25, 0.06, 0.5, 0.015])
    depth = (-sub).where(sub < 0)
    m = ax.pcolormesh(sub.lon, sub.lat, depth, cmap="Blues", vmin=0, vmax=6500, shading="auto",
                      rasterized=True)
    ax.pcolormesh(sub.lon, sub.lat, sub.where(sub >= 0) * 0, cmap="Greys", vmin=-1, vmax=8,
                  shading="auto", rasterized=True)
    ax.contour(sub.lon, sub.lat, depth, levels=[DEPTH_QUALIFIED], colors="#222222", linewidths=0.3)
    ax.set_aspect(1 / np.cos(np.radians(15)))
    cable = st.GROUPS["Brazil cable"]
    # other landing points in neutral grey underneath, the agreed one on top
    for agreed in (False, True):
        for _, r in routes.iterrows():
            if r.route.startswith(BR_AGREED) != agreed or "Wilhelmshaven" not in r.route:
                continue
            ch = ", Channel," in r.route
            sh = r.route.endswith("shallow")
            col = (cable if ch else "#222222") if agreed else st.NEUTRAL
            ax.plot(*r.geometry.xy, color=col, lw=(1.0 if sh else 0.7) if agreed else 0.4,
                    ls="-" if sh else (0, (2, 1.5)), zorder=3 if agreed else 2)
    for name, (la, lo) in {**LANDING_BR, **LANDING_DE}.items():
        ax.plot(lo, la, "o", ms=3, color="#222222", zorder=4)
    st.map_axes(ax)
    ax.set_title("Candidate cable routes Natal-Wilhelmshaven", loc="left")
    st.legend_squares(ax, [(cable, "via English Channel"), ("#222222", "around Scotland"),
                           (st.NEUTRAL, "other Brazilian landing points")], loc="lower left")
    ax.text(0.01, 0.15, "solid: depth-aware, dashed: shortest; thin line: 3,000 m isobath",
            transform=ax.transAxes, fontsize=7, color="#aaaaaa")
    st.colorbar(fig, m, cax, "Water depth, m")
    fig.savefig(OUT / "routes_map.png", dpi=300)
    fig.savefig(OUT / "routes_map.pdf")

    # depth profiles of the four Natal-Wilhelmshaven variants, one panel each
    sel = df[(df.brazil == BR_AGREED) & (df.germany == "Wilhelmshaven")]
    fig, axes = plt.subplots(4, 1, figsize=(5.6, 6.4), sharex=True, sharey=True)
    for ax, (_, r) in zip(axes, sel.sort_values(["corridor", "variant"]).iterrows()):
        p = prof[prof.route == r.route]
        ax.fill_between(p.km, p.depth_m, color=cable if r.corridor == "Channel" else "#222222",
                        lw=0, alpha=0.85)
        ax.text(0.99, 0.08, f"{r.corridor}, {'depth-aware' if r.variant == 'shallow' else 'shortest'}: "
                f"{r.length_km:,.0f} km, max {r.max_depth_m:,.0f} m",
                transform=ax.transAxes, ha="right", fontsize=7.5, color="#222222")
        for d in (DEPTH_LAID, DEPTH_QUALIFIED):
            ax.axhline(d, color="#aaaaaa", lw=0.6, ls=(0, (2, 2)))
        ax.set_ylim(7000, 0)
    axes[0].text(50, DEPTH_LAID - 150, "deepest laid, 2,150 m", fontsize=7, color="#aaaaaa")
    axes[0].text(50, DEPTH_QUALIFIED + 650, "deepest qualified, 3,000 m", fontsize=7, color="#aaaaaa")
    axes[0].set_title("Water depth along the cable route Natal-Wilhelmshaven, m", loc="left")
    axes[-1].set_xlabel("Distance from Natal, km")
    fig.savefig(OUT / "depth_profile.png", dpi=300)
    fig.savefig(OUT / "depth_profile.pdf")


if __name__ == "__main__":
    main()
