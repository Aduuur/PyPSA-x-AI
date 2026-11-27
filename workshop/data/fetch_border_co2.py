# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Hourly CO2 intensity of the power generated in Germany's neighbours.

Used to count the emissions of imports in the German CO2 cap
(``scripts/add_border_trade.py``, ``data/custom_extra_functionality.py``).

Method (average, attributional emission factor, as used for consumption-based
accounting of electricity imports):

    intensity_z(t) = sum_f gen_{z,f}(t) * EF_f / sum_f gen_{z,f}(t)    [tCO2/MWh_el]

- gen: hourly net public generation by production type, energy-charts.info API
  (Fraunhofer ISE; data from ENTSO-E Transparency Platform), licence CC BY 4.0.
  The API gives countries, not bidding zones: DK1 and DK2 use Denmark, NO2
  Norway, SE4 Sweden.
- EF_f = fuel CO2 intensity / electric efficiency, both taken from the model's
  own cost data (``data/costs/archive/v0.15.0/costs_2025.csv``), so imports are
  rated with the same assumptions as German plants: hard coal (``coal``),
  lignite (``lignite``), fossil gas (``gas`` with ``CCGT`` efficiency), oil
  (``oil``). All other types (nuclear, hydro, wind, solar, biomass, waste,
  others) count as zero.
- Pumped storage (generation and consumption), cross-border trade and load
  rows are left out of the generation total.

Known simplifications: new-plant efficiencies are higher than fleet averages and
waste is counted as zero, so the intensity is rather a lower bound; all fuel of
CHP plants is assigned to power; each zone's intensity ignores its own imports.

    pixi run python workshop/data/fetch_border_co2.py [year] [output.csv]
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.energy-charts.info/public_power"
ROOT = Path(__file__).resolve().parents[2]
COSTS = ROOT / "data/costs/archive/v0.15.0/costs_2025.csv"

# bidding zone (column of the price file) -> energy-charts country code
ZONES = {
    "NL": "nl", "BE": "be", "FR": "fr", "CH": "ch", "AT": "at", "CZ": "cz",
    "PL": "pl", "DK1": "dk", "DK2": "dk", "NO2": "no", "SE4": "se",
}  # fmt: skip

# production type (lower case, first match wins) -> fuel in the cost data
FOSSIL = [
    ("brown coal", "lignite"),
    ("lignite", "lignite"),
    ("peat", "lignite"),
    ("coal-derived gas", "coal"),
    ("hard coal", "coal"),
    ("gas", "gas"),
    ("oil", "oil"),
]
NOT_GENERATION = ("load", "residual", "share", "cross border", "pumped storage")


def emission_factors():
    """tCO2 per MWh of electricity by fuel, from the model's cost data."""
    c = pd.read_csv(COSTS, index_col=[0, 1])["value"]
    eff = {"coal": c["coal", "efficiency"], "lignite": c["lignite", "efficiency"],
           "gas": c["CCGT", "efficiency"], "oil": c["oil", "efficiency"]}
    return {f: c[f, "CO2 intensity"] / e for f, e in eff.items()}


def fetch(country, year, retries=6):
    for attempt in range(retries):
        r = requests.get(
            API,
            params={"country": country, "start": f"{year}-01-01T00:00Z", "end": f"{year}-12-31T23:59Z"},
            timeout=300,
        )
        if r.status_code != 429:  # the API rate-limits: back off and retry
            break
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    d = r.json()
    idx = pd.to_datetime(d["unix_seconds"], unit="s")
    gen = {p["name"]: p["data"] for p in d["production_types"]}
    return pd.DataFrame(gen, index=idx, dtype=float).resample("h").mean()


def intensity(gen, ef):
    gen = gen[[c for c in gen.columns if not any(k in c.lower() for k in NOT_GENERATION)]].clip(lower=0)
    emis = pd.Series(0.0, index=gen.index)
    for col in gen.columns:
        fuel = next((f for key, f in FOSSIL if key in col.lower()), None)
        if fuel:
            emis += gen[col].fillna(0) * ef[fuel]
    total = gen.sum(axis=1, min_count=1)
    return emis / total, emis.sum() / total.sum()


def main(year=2024, out=None):
    out = Path(out or Path(__file__).with_name(f"border_co2_intensity_{year}.csv"))
    ef = emission_factors()
    print("emission factors, tCO2/MWh_el:", {k: round(v, 3) for k, v in ef.items()})
    cache, cols, annual = {}, {}, {}
    for zone, country in ZONES.items():
        if country not in cache:
            cache[country] = intensity(fetch(country, year), ef)
            time.sleep(5)
        cols[zone], annual[zone] = cache[country]
    idx = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h")
    df = pd.DataFrame(cols).reindex(idx).interpolate(limit=6).ffill().bfill().round(4)
    df.index.name = "utc_timestamp"
    if df.isna().any().any():
        raise ValueError(f"gaps left after interpolation:\n{df.isna().sum()}")
    df.to_csv(out)
    print(f"{out}: {len(df)} hours, {df.shape[1]} zones")
    print("generation-weighted annual mean, tCO2/MWh:", {k: round(v, 3) for k, v in annual.items()})


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2024, sys.argv[2] if len(sys.argv) > 2 else None)
