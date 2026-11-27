# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT

"""
Light-weight trade with neighbouring countries for a single-country model.

Each border gets two fixed-capacity generators at its German node:

- ``border trade in``: buys power from the neighbour at the neighbour's hourly
  price (plus a small hurdle cost), up to the import transfer capacity;
- ``border trade out``: sells power to the neighbour (negative output only) and
  earns the neighbour's price (minus the hurdle cost), up to the export
  transfer capacity.

The neighbours' prices are exogenous: the neighbours do not react to German
imports or exports. Historical prices are moved onto the model's weather year
with matching weekdays, then averaged to the model's time steps and scaled per
planning horizon.

The carrier names avoid the word "import" on purpose: ``solve_network.py``
treats every carrier containing "import" as a sector import.
"""

import logging

import numpy as np
import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

CARRIER_IN = "border trade in"
CARRIER_OUT = "border trade out"
CARRIERS = {
    CARRIER_IN: dict(nice_name="Border trade in", color="#8c8c8c"),
    CARRIER_OUT: dict(nice_name="Border trade out", color="#b5b5b5"),
}


def _by_horizon(value, horizon, default):
    """Return value[horizon] for a {year: value} mapping, else value itself."""
    if value is None:
        return default
    if isinstance(value, dict):
        value = {int(k): v for k, v in value.items()}
        if horizon not in value:
            raise KeyError(f"border_trade: no value for horizon {horizon} in {value}")
        return value[horizon]
    return value


def align_prices_to_snapshots(prices: pd.DataFrame, snapshots: pd.DatetimeIndex):
    """
    Map hourly prices of any year onto the model snapshots.

    The price year is shifted so weekdays match the model year (Tuesday stays
    Tuesday), wrapping around at the end. The hourly values are then averaged
    over each model time step (e.g. 2 h), whatever the step length.
    """
    prices = prices.sort_index()
    step = snapshots[1] - snapshots[0] if len(snapshots) > 1 else pd.Timedelta("1h")
    hours = pd.date_range(snapshots[0], snapshots[-1] + step, freq="h", inclusive="left")
    hours = hours[hours.isin(snapshots) | ~((hours.month == 2) & (hours.day == 29))]

    first_day = prices.index[0].normalize()
    offset = (hours[0].weekday() - first_day.weekday()) % 7
    start = first_day + pd.Timedelta(days=offset)
    values = prices.loc[start:].to_numpy()
    values = np.concatenate([values, prices.loc[: start - pd.Timedelta("1h")].to_numpy()])
    values = np.resize(values, (len(hours), prices.shape[1]))
    hourly = pd.DataFrame(values, index=hours, columns=prices.columns)

    position = snapshots.searchsorted(hourly.index, side="right") - 1
    aligned = hourly.groupby(position).mean()
    aligned.index = snapshots[aligned.index]
    return aligned.reindex(snapshots).ffill().bfill()


def add_border_trade(n: pypsa.Network, prices_fn: str, config: dict, horizon: int):
    """Attach import and export options at the border nodes of the network."""
    borders = config.get("borders", {})
    if not borders:
        logger.warning("border_trade is enabled but no borders are configured")
        return

    raw = pd.read_csv(prices_fn, index_col=0, parse_dates=True)
    zones = sorted({b["zone"] for b in borders.values()})
    missing = set(zones) - set(raw.columns)
    if missing:
        raise KeyError(f"border_trade: zones {missing} not in {prices_fn}")
    prices = align_prices_to_snapshots(raw[zones], n.snapshots)

    scale = float(_by_horizon(config.get("price_scaling"), horizon, 1.0))
    capacity_scale = float(_by_horizon(config.get("capacity_scaling"), horizon, 1.0))
    hurdle = float(config.get("hurdle_cost", 0.0))
    floor, cap = config.get("price_floor"), config.get("price_cap")
    prices = (prices * scale).clip(lower=floor, upper=cap)

    for carrier, attrs in CARRIERS.items():
        if carrier not in n.carriers.index:
            n.add("Carrier", carrier, co2_emissions=0.0, **attrs)

    for name, b in borders.items():
        bus = b["bus"]
        if bus not in n.buses.index:
            raise KeyError(f"border_trade: bus '{bus}' of border '{name}' not in network")
        price = prices[b["zone"]]
        p_in = float(b.get("p_nom_in", b.get("p_nom", 0.0))) * capacity_scale
        p_out = float(b.get("p_nom_out", b.get("p_nom", 0.0))) * capacity_scale
        if p_in > 0:
            n.add(
                "Generator",
                f"{name} {CARRIER_IN}",
                bus=bus,
                carrier=CARRIER_IN,
                p_nom=p_in,
                p_nom_extendable=False,
                marginal_cost=price + hurdle,
            )
        if p_out > 0:
            n.add(
                "Generator",
                f"{name} {CARRIER_OUT}",
                bus=bus,
                carrier=CARRIER_OUT,
                p_nom=p_out,
                p_nom_extendable=False,
                p_min_pu=-1.0,
                p_max_pu=0.0,
                marginal_cost=price - hurdle,
            )

    logger.info(
        f"Border trade {horizon}: {len(borders)} borders, "
        f"{sum(float(b.get('p_nom_in', b.get('p_nom', 0))) for b in borders.values()) * capacity_scale / 1e3:.1f} GW in, "
        f"{sum(float(b.get('p_nom_out', b.get('p_nom', 0))) for b in borders.values()) * capacity_scale / 1e3:.1f} GW out, "
        f"price scaling {scale}, mean price {prices.mean().mean():.1f} EUR/MWh"
    )
