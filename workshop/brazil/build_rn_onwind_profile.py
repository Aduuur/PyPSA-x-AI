# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Hourly onshore wind capacity factor for Rio Grande do Norte (RN), 2013, UTC.

1. ERA5 capacity factor per grid cell (atlite, Vestas V112 3 MW), averaged over
   the cells whose centre lies inside the state of RN.
2. Scaled to the level of the RN wind farms measured by the grid operator ONS:
   factor = measured capacity factor / ERA5 capacity factor, both over the
   hours in which the farms report. Farms used: they report (nearly) the whole
   year and have units in operation on 2013-12-31 in the ONS plant register.
   Scaled values are clipped at 1 per cell and hour.

Uses only the Brazil workshop data (`data-brazil/`, see its README.md); it
reads no file from `workshop/inputs/`. Writes to `resources/brazil/`, which git
ignores. Takes about 10 seconds and under 1 GB of memory (the cutout is cut
to the RN box before any calculation).

    pixi run python workshop/brazil/build_rn_onwind_profile.py
"""

from pathlib import Path

import atlite
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely import contains_xy

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data-brazil"
OUT = ROOT / "resources" / "brazil"

STATE = "RN"
YEAR = 2013
TURBINE = "Vestas_V112_3MW"
MIN_REPORTED_HOURS = 8000  # farms must report (nearly) the whole year
REGISTER_DATE = pd.Timestamp(f"{YEAR}-12-31")


def ons_local_to_utc(s: pd.Series) -> pd.Series:
    """ONS time stamps (Brasilia legal time with DST) to naive UTC."""
    idx = s.index.tz_localize(
        "America/Sao_Paulo", ambiguous=True, nonexistent="shift_forward"
    )
    s = s.set_axis(idx.tz_convert("UTC").tz_localize(None))
    return s[~s.index.duplicated()]


def state_shape(uf: str):
    gadm = gpd.read_file(f"zip://{DATA}/raw/gadm/gadm41_BRA_1.json.zip")
    gadm["UF"] = gadm["HASC_1"].str.split(".").str[1]
    return gadm.set_index("UF").loc[uf, "geometry"].buffer(0)


def era5_cell_cf(shape) -> pd.DataFrame:
    """Hourly capacity factor of every ERA5 cell inside the shape (time x cells)."""
    cutout = atlite.Cutout(DATA / "weather" / "brazil-2013-era5.nc")
    minx, miny, maxx, maxy = shape.bounds
    pad = 0.5
    cutout = cutout.sel(x=slice(minx - pad, maxx + pad), y=slice(miny - pad, maxy + pad))
    cf = cutout.wind(turbine=TURBINE, aggregate_time=None).transpose("time", "y", "x")
    xs, ys = np.meshgrid(cf.x.values, cf.y.values)
    inside = contains_xy(shape, xs, ys)
    values = cf.values[:, inside]
    return pd.DataFrame(values, index=pd.DatetimeIndex(cf.time.values))


def measured_farm_cf(uf: str) -> tuple[pd.Series, int, float]:
    """Hourly capacity factor of the measured wind fleet of a state (UTC)."""
    gen = pd.read_parquet(
        DATA / "raw" / "ons" / f"GERACAO_USINA-2_{YEAR}.parquet",
        columns=["din_instante", "id_estado", "nom_tipousina", "ceg", "val_geracao"],
    )
    gen = gen[
        (gen.nom_tipousina.str.strip() == "EOLIELÉTRICA")
        & (gen.id_estado.str.strip() == uf)
    ].copy()
    gen["mw"] = gen.val_geracao.astype(float)
    gen["t"] = pd.to_datetime(gen.din_instante)

    reg = pd.read_csv(DATA / "raw" / "ons" / "CAPACIDADE_GERACAO.csv", sep=";", dtype=str)
    reg = reg[reg.nom_tipousina.str.strip() == "EOLIELÉTRICA"].copy()
    reg["mw"] = reg.val_potenciaefetiva.astype(float)
    start = pd.to_datetime(reg.dat_entradaoperacao, errors="coerce")
    end = pd.to_datetime(reg.dat_desativacao, errors="coerce")
    in_operation = (start <= REGISTER_DATE) & (end.isna() | (end > REGISTER_DATE))
    capacity = reg[in_operation].groupby("ceg").mw.sum()  # all units of a farm

    hours = gen.groupby("ceg").t.nunique()
    farms = [
        c for c in hours.index
        if hours[c] >= MIN_REPORTED_HOURS and capacity.get(c, 0.0) > 0
    ]
    gen = gen[gen.ceg.isin(farms)]
    fleet_mw = float(capacity[farms].sum())
    # hours in which all selected farms report
    per_hour = gen.groupby("t").agg(mw=("mw", "sum"), n=("ceg", "nunique"))
    per_hour = per_hour[per_hour.n == len(farms)]
    cf = ons_local_to_utc(per_hour.mw.sort_index() / fleet_mw)
    return cf, len(farms), fleet_mw


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    snapshots = pd.date_range(f"{YEAR}-01-01", f"{YEAR}-12-31 23:00", freq="h")

    shape = state_shape(STATE)
    cells = era5_cell_cf(shape).reindex(snapshots)
    era5 = cells.mean(axis=1)

    measured, n_farms, fleet_mw = measured_farm_cf(STATE)
    measured = measured.reindex(snapshots).dropna()
    factor = measured.mean() / era5.loc[measured.index].mean()

    scaled_cells = (cells * factor).clip(upper=1.0)
    profile = scaled_cells.mean(axis=1)

    out = pd.DataFrame(
        {
            "timestamp_utc": snapshots.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "rn_onwind_cf": profile.round(4).values,
        }
    )
    path = OUT / f"{STATE.lower()}_onwind_cf_{YEAR}_utc.csv"
    out.to_csv(path, index=False)

    both = pd.DataFrame({"measured": measured, "profile": profile}).dropna()
    daily = both.resample("D").mean()
    monthly = both.resample("MS").mean()
    print(f"ERA5 cells inside {STATE}: {cells.shape[1]}")
    print(f"measured farms: {n_farms}, {fleet_mw:.0f} MW, {len(measured)} hours")
    print(f"mean CF  ERA5 {era5.mean():.3f}  measured {measured.mean():.3f}  "
          f"factor {factor:.3f}  profile {profile.mean():.3f}")
    print(f"cell-hours clipped at 1: {((cells * factor) > 1).values.mean():.3f}")
    print(f"correlation monthly {monthly.measured.corr(monthly.profile):.2f}  "
          f"daily {daily.measured.corr(daily.profile):.2f}  "
          f"hourly {both.measured.corr(both.profile):.2f}")
    print(f"written {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
