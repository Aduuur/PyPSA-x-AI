# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Download hourly day-ahead prices of Germany's neighbouring bidding zones.

Source: energy-charts.info API (Fraunhofer ISE), data from Bundesnetzagentur |
SMARD.de, licence CC BY 4.0. Writes one column per bidding zone in EUR/MWh,
UTC, hourly (15-minute prices are averaged to the hour).

    pixi run python workshop/data/fetch_border_prices.py [year] [output.csv]
"""

import sys
import time
from pathlib import Path

import pandas as pd
import requests

API = "https://api.energy-charts.info/price"
ZONES = ["DE-LU", "NL", "BE", "FR", "CH", "AT", "CZ", "PL", "DK1", "DK2", "NO2", "SE4"]


def fetch(zone, year, retries=6):
    for attempt in range(retries):
        r = requests.get(
            API,
            params={"bzn": zone, "start": f"{year}-01-01T00:00Z", "end": f"{year}-12-31T23:59Z"},
            timeout=120,
        )
        if r.status_code != 429:  # the API rate-limits: back off and retry
            break
        time.sleep(15 * (attempt + 1))
    r.raise_for_status()
    d = r.json()
    s = pd.Series(d["price"], index=pd.to_datetime(d["unix_seconds"], unit="s"), dtype=float)
    return s.resample("h").mean()


def main(year=2024, out=None):
    out = Path(out or Path(__file__).with_name(f"border_prices_{year}.csv"))
    cols = {}
    for z in ZONES:
        cols[z.replace("-", "_")] = fetch(z, year)
        time.sleep(5)
    idx = pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h")
    df = pd.DataFrame(cols).reindex(idx).interpolate(limit=6).round(2)
    df.index.name = "utc_timestamp"
    if df.isna().any().any():
        raise ValueError(f"gaps left after interpolation:\n{df.isna().sum()}")
    df.to_csv(out)
    print(f"{out}: {len(df)} hours, {df.shape[1]} zones")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2024, sys.argv[2] if len(sys.argv) > 2 else None)
