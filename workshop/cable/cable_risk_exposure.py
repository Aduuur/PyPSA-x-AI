# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Exposure of the cable route cases to risks that can be measured from public
data (Role 1). Feeds RISKS.md.

Per route case (from cable_route.py, run that first):

- km inside each country's exclusive economic zone (EEZ) and on the high
  seas: who has to consent (UNCLOS Art. 79: route on the continental shelf
  needs coastal-state consent; Art. 87/112: freedom to lay on the high seas).
- km in shelf water (<= 200 m: anchors, fishing, the most frequent cause of
  cable faults), on the slope (200-2,150 m), beyond the deepest cable laid
  (2,150 m), beyond the qualified depth (3,000 m).
- km on steep seabed (slope > 10 %, from the 30" grid: canyons, scarps,
  landslide and turbidity-current risk).
- Closest approach to Fernando de Noronha, Atol das Rocas, St Peter and St Paul (Brazilian marine
  protected areas, public coordinates).

Data: GEBCO_2025 (public domain), Marine Regions World EEZ v12 low-res
(CC-BY 4.0, Flanders Marine Institute 2023), already in data/eez/.

Output: workshop/cable/results/risk_exposure.csv (tracked) and
results/cable/risk_exposure_by_eez.csv.

    pixi run python workshop/cable/cable_risk_exposure.py
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import xarray as xr
from shapely.geometry import Point

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "workshop/plotstyle").is_dir())
OUT = ROOT / "results/cable"
SHARED = ROOT / "workshop/cable/results"
BATHY = ROOT / "data-brazil/bathymetry_atlantic/gebco_2025_atlantic_30s.nc"
EEZ = ROOT / "data/eez/archive/v12_20231025/World_EEZ_v12_20231025_LR/eez_v12_lowres.gpkg"

R_EARTH = 6371.0
# Marine protected areas off RN (public, lon, lat).
MPA = {"Fernando de Noronha": (-32.42, -3.85), "Atol das Rocas": (-33.81, -3.86),
       "St Peter and St Paul": (-29.35, 0.92)}


def haversine(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = p2 - p1, np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * R_EARTH * np.arcsin(np.sqrt(a))


def slope_grid(da):
    """Seabed slope (m/m) on the 30" grid."""
    z = da.values.astype(float)
    lat = np.radians(da.lat.values)
    dy = np.radians(abs(float(da.lat[1] - da.lat[0]))) * R_EARTH * 1e3
    dx = np.radians(abs(float(da.lon[1] - da.lon[0]))) * R_EARTH * 1e3 * np.cos(lat)[:, None]
    gy, gx = np.gradient(z)
    return xr.DataArray(np.hypot(gx / dx, gy / dy), coords=da.coords, dims=da.dims)


def main():
    cases = pd.read_csv(OUT / "cases.csv", index_col=0)
    routes = gpd.read_file(OUT / "routes.gpkg").set_index("route")
    elev = xr.open_dataset(BATHY).elevation
    eez = gpd.read_file(EEZ)[["SOVEREIGN1", "TERRITORY1", "geometry"]]

    rows, by_eez = [], []
    for case, r in cases.iterrows():
        line = routes.geometry[r.route]
        lon, lat = np.array(line.xy)
        seg = haversine(lat[:-1], lon[:-1], lat[1:], lon[1:])
        km = np.r_[0, np.cumsum(seg)]
        s = np.arange(0, km[-1], 2.0)
        slat, slon = np.interp(s, km, lat), np.interp(s, km, lon)
        step = np.diff(np.r_[s, km[-1]])

        win = elev.sel(lat=slice(slat.min() - 0.1, slat.max() + 0.1),
                       lon=slice(slon.min() - 0.1, slon.max() + 0.1))
        z = win.interp(lat=("p", slat), lon=("p", slon), method="nearest").values
        depth = np.clip(-z, 0, None)
        slope = slope_grid(win).interp(lat=("p", slat), lon=("p", slon), method="nearest").values

        pts = gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in zip(slon, slat)], crs="EPSG:4326")
        j = gpd.sjoin(pts, eez, how="left", predicate="within")
        j = j[~j.index.duplicated()]
        zone = j.SOVEREIGN1.fillna("High seas")
        km_zone = pd.Series(step, index=j.index).groupby(zone.values).sum().sort_values(ascending=False)
        for k, v in km_zone.items():
            by_eez.append(dict(case=case, zone=k, km=round(v)))

        mpa = {f"min_dist_{k.replace(' ', '_')}_km": haversine(y, x, slat, slon).min()
               for k, (x, y) in MPA.items()}
        rows.append(dict(
            case=case, length_km=r.length_km,
            km_shelf_le200m=step[depth <= 200].sum(),
            km_slope_200_2150m=step[(depth > 200) & (depth <= 2150)].sum(),
            km_beyond_laid_2150m=step[depth > 2150].sum(),
            km_beyond_qualified_3000m=step[depth > 3000].sum(),
            km_steep_slope_gt10pct=step[slope > 0.10].sum(),
            km_high_seas=km_zone.get("High seas", 0.0),
            km_in_foreign_eez=km_zone.drop(["High seas", "Brazil", "Germany"], errors="ignore").sum(),
            n_foreign_eez=len(km_zone.drop(["High seas", "Brazil", "Germany"], errors="ignore")),
            foreign_eez=", ".join(km_zone.drop(["High seas", "Brazil", "Germany"], errors="ignore").index),
            **mpa,
        ))

    df = pd.DataFrame(rows).round(0)
    SHARED.mkdir(parents=True, exist_ok=True)
    df.to_csv(SHARED / "risk_exposure.csv", index=False)
    ez = pd.DataFrame(by_eez)
    ez.to_csv(OUT / "risk_exposure_by_eez.csv", index=False)
    ez.to_csv(SHARED / "risk_exposure_by_eez.csv", index=False)
    pd.set_option("display.width", 250)
    print(df.drop(columns="foreign_eez").to_string(index=False))
    print()
    print(ez.pivot(index="zone", columns="case", values="km").fillna(0).astype(int)
          .sort_values("reference", ascending=False).to_string())


if __name__ == "__main__":
    main()
