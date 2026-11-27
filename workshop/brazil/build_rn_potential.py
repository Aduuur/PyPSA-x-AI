# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Renewable potential and hourly profiles for Rio Grande do Norte (RN), 2013, UTC.

Follows PyPSA-Eur (``determine_availability_matrix_MD_UA.py`` and
``build_renewable_profiles.py``) with the Brazil workshop data:

- Land eligibility from Copernicus LC100 with PyPSA-Eur's class mapping outside
  CORINE, and protected areas (WDPA) excluded. Exclusion grid of 100 m in
  South America Albers (ESRI:102033).
- Capacity density as in ``config/config.default.yaml``.
- Onshore wind in 3 resource classes of equal capacity-factor width, as in the
  workshop baseline; layout proportional to capacity factor x eligible area.
  Scaled to ONS-measured RN wind farms with the factor from
  ``build_rn_onwind_profile.py`` (the same factor for every class).
- Solar with single-axis tracking (horizontal north-south axis), one class,
  not scaled: there is no measured solar generation in RN for 2013.

Wind and solar compete for the same land: do not add their potentials.

Uses only ``data-brazil/``; reads no file from ``workshop/inputs/``. Writes to
``resources/brazil/`` (git-ignored). About 45 seconds, under 2 GB memory.

    pixi run python workshop/brazil/build_rn_potential.py
"""

import sys
from pathlib import Path

import atlite
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_rn_onwind_profile import (  # noqa: E402
    DATA,
    OUT,
    ROOT,
    STATE,
    YEAR,
    era5_cell_cf,
    measured_farm_cf,
    state_shape,
)

CRS_AREA = "ESRI:102033"  # South America Albers equal area
ONWIND = dict(
    turbine="Vestas_V112_3MW",
    capacity_per_sqkm=3.0,
    codes=[20, 30, 40, 60, 100],  # shrubs, herbaceous, cropland, bare, moss
    settlement_buffer_m=1000,  # around LC100 class 50 (urban)
    classes=3,
)
SOLAR_HSAT = dict(
    panel="CSi",
    orientation={"slope": 35.0, "azimuth": 180.0},  # axis azimuth: north-south
    tracking="horizontal",
    capacity_per_sqkm=4.43,
    codes=[20, 30, 40, 50, 60, 90, 100],
)


def clip_layers(shape, workdir: Path):
    """Cut land cover and protected areas to the state box (local files)."""
    minx, miny, maxx, maxy = shape.bounds
    pad = 0.1
    box = (minx - pad, miny - pad, maxx + pad, maxy + pad)
    lc_path = workdir / "lc100_clip.tif"
    with rasterio.open(DATA / "layers" / "copernicus_lc100.tif") as src:
        window = from_bounds(*box, src.transform)
        band = src.read(1, window=window)
        profile = src.profile.copy()
        profile.update(
            width=band.shape[1],
            height=band.shape[0],
            transform=src.window_transform(window),
            compress="lzw",
        )
    with rasterio.open(lc_path, "w", **profile) as dst:
        dst.write(band, 1)

    wdpa_path = workdir / "wdpa_clip.gpkg"
    wdpa = gpd.read_file(DATA / "layers" / "wdpa_brazil.gpkg", bbox=box)
    wdpa = wdpa[wdpa.geometry.notna()][["geometry"]].to_crs(CRS_AREA)
    wdpa.to_file(wdpa_path)
    return lc_path, wdpa_path


def eligible_km2(cutout, shape, lc_path, wdpa_path, codes, settlement_buffer_m=0):
    """Eligible area per cutout cell in km2 (y, x)."""
    excluder = atlite.ExclusionContainer(crs=CRS_AREA, res=100)
    excluder.add_raster(lc_path, codes=codes, invert=True, crs="EPSG:4326")
    if settlement_buffer_m:
        excluder.add_raster(
            lc_path, codes=[50], buffer=settlement_buffer_m, crs="EPSG:4326"
        )
    excluder.add_geometry(wdpa_path)
    shares = cutout.availabilitymatrix(gpd.GeoSeries([shape], crs=4326), excluder)
    shares = shares.squeeze(drop=True)
    cell_km2 = cutout.grid.set_index(["y", "x"]).to_crs(CRS_AREA).area / 1e6
    return shares * cell_km2.to_xarray()


def weighted_profile(cf_t: xr.DataArray, weight: xr.DataArray) -> pd.Series:
    """Hourly profile of a layout (weights over y, x)."""
    profile = (cf_t * weight).sum(["y", "x"]) / weight.sum()
    return profile.to_series()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshots = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h")
    shape = state_shape(STATE)
    minx, miny, maxx, maxy = shape.bounds
    cutout = atlite.Cutout(DATA / "weather" / "brazil-2013-era5.nc")
    cutout = cutout.sel(x=slice(minx - 0.5, maxx + 0.5), y=slice(miny - 0.5, maxy + 0.5))
    lc_path, wdpa_path = clip_layers(shape, OUT)
    state_km2 = gpd.GeoSeries([shape], crs=4326).to_crs(CRS_AREA).area.iloc[0] / 1e6

    # scaling factor for wind, as in build_rn_onwind_profile.py
    era5_state = era5_cell_cf(shape).reindex(snapshots).mean(axis=1)
    measured, _, _ = measured_farm_cf(STATE)
    measured = measured.reindex(snapshots).dropna()
    factor = measured.mean() / era5_state.loc[measured.index].mean()

    rows, profiles = [], {}

    # onshore wind, resource classes
    wind_t = cutout.wind(turbine=ONWIND["turbine"], aggregate_time=None)
    wind_t = wind_t.transpose("time", "y", "x")
    wind_scaled_t = (wind_t * factor).clip(max=1.0)
    km2 = eligible_km2(
        cutout, shape, lc_path, wdpa_path, ONWIND["codes"], ONWIND["settlement_buffer_m"]
    ).reindex_like(wind_t.isel(time=0)).fillna(0.0)
    cf = wind_t.mean("time")
    eligible = km2 > 0
    lo = float(cf.where(eligible).min()) - 1e-3
    hi = float(cf.where(eligible).max()) + 1e-3
    edges = lo + (hi - lo) * np.linspace(0, 1, ONWIND["classes"] + 1)
    for b in range(ONWIND["classes"]):
        in_class = eligible & (cf >= edges[b]) & (cf < edges[b + 1])
        weight = (km2 * cf).where(in_class, 0.0)
        name = f"onwind class {b}"
        profiles[name] = weighted_profile(wind_scaled_t, weight)
        rows.append(
            {
                "carrier": "onwind",
                "class": b,
                "eligible_km2": float(km2.where(in_class, 0.0).sum()),
                "p_nom_max_mw": ONWIND["capacity_per_sqkm"]
                * float(km2.where(in_class, 0.0).sum()),
                "cf_unscaled": float(weighted_profile(wind_t, weight).mean()),
                "cf": float(profiles[name].mean()),
            }
        )

    # solar, single-axis tracking, one class
    pv_t = cutout.pv(
        panel=SOLAR_HSAT["panel"],
        orientation=SOLAR_HSAT["orientation"],
        tracking=SOLAR_HSAT["tracking"],
        aggregate_time=None,
    ).transpose("time", "y", "x")
    km2 = eligible_km2(
        cutout, shape, lc_path, wdpa_path, SOLAR_HSAT["codes"]
    ).reindex_like(pv_t.isel(time=0)).fillna(0.0)
    weight = km2 * pv_t.mean("time")
    profiles["solar-hsat"] = weighted_profile(pv_t, weight)
    rows.append(
        {
            "carrier": "solar-hsat",
            "class": 0,
            "eligible_km2": float(km2.sum()),
            "p_nom_max_mw": SOLAR_HSAT["capacity_per_sqkm"] * float(km2.sum()),
            "cf_unscaled": float(profiles["solar-hsat"].mean()),
            "cf": float(profiles["solar-hsat"].mean()),
        }
    )

    table = pd.DataFrame(rows)
    table["eligible_share_of_state"] = table.eligible_km2 / state_km2
    table = table.round(
        {"eligible_km2": 0, "p_nom_max_mw": 0, "cf_unscaled": 3, "cf": 3,
         "eligible_share_of_state": 3}
    )
    table.to_csv(OUT / f"{STATE.lower()}_potential_{YEAR}.csv", index=False)

    out = pd.DataFrame(profiles).reindex(snapshots).round(4)
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    out.index.name = "timestamp_utc"
    out.to_csv(OUT / f"{STATE.lower()}_profiles_{YEAR}_utc.csv")

    print(f"wind scaling factor {factor:.3f}")
    print(table.to_string(index=False))
    print(f"written {(OUT / f'{STATE.lower()}_potential_{YEAR}.csv').relative_to(ROOT)}")
    print(f"written {(OUT / f'{STATE.lower()}_profiles_{YEAR}_utc.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
