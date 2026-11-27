# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Add the Brazilian supply in Rio Grande do Norte to a composed network (Role 2).

Called from ``scripts/compose_network.py`` for every horizon, before the cable
(``workshop/cable/add_brazil_cable.py``). Does nothing unless the config says
``brazil_supply: {enable: true}``, so the baseline and every other run stay
unchanged.

What it adds:

- The AC bus ``Brazil Natal`` (``country: BR``) at the cable's landing point,
  agreed with role 1. It is added in **every** horizon where it is missing:
  under myopic foresight the brownfield step carries the cable over from the
  previous horizon, but not the bus.
- From the start year on (default: the cable's build year), extendable
  generators per resource class, carriers ``Brazil onwind`` and
  ``Brazil solar-hsat``. Names follow PyPSA-Eur with the build year as
  suffix, e.g. ``Brazil Natal onwind 2-2040``. Capacity built in earlier
  horizons is carried over by the brownfield step and subtracted from the
  potential here.

Inputs are written by ``workshop/brazil/build_rn_potential.py`` to
``resources/brazil/`` (git-ignored); run it once in your workspace. Snakemake
does not track these files: after rebuilding them, rerun with
``--forcerun compose_network``.

Costs: the processed cost data of the horizon (``onwind``, ``solar-hsat``),
annualised like every German generator, plus the onshore connection to the
converter (``HVAC overhead`` x distance x ``lines.length_factor``), as
PyPSA-Eur does for the offshore wind connection. Cost basis agreed with role 4:
EUR 2025, lifetimes of the cost data, discount rate from the cost data (7 % in
the main runs). The values are the European ones for now (role 4's comparison
case), **placeholders** for the Brazilian sources (see the README).

Carriers are ``Brazil onwind`` and ``Brazil solar-hsat`` on purpose (role 2's
decision): constraints written per carrier for Germany must not include them.

Config (all optional except enable):

    brazil_supply:
      enable: true
      bus: Brazil Natal
      start_year: 2040        # default: brazil_cable.build_year, else the cable file
      carriers: [onwind, solar-hsat]
      connection_cost: true
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
POTENTIAL = ROOT / "resources" / "brazil" / "rn_potential_2013.csv"
PROFILES = ROOT / "resources" / "brazil" / "rn_profiles_2013_utc.csv"
CABLE_PARAMETERS = ROOT / "workshop" / "cable" / "cable_parameters.yaml"

DEFAULT_BUS = "Brazil Natal"
NATAL = (-35.20, -5.78)  # lon, lat; the landing point in add_brazil_cable.py
# technology in the potential table -> cost entry and plotting colour
TECHNOLOGIES = {"onwind": "onwind", "solar-hsat": "solar-hsat"}


def start_year(config: dict, cfg: dict) -> int:
    """First horizon with Brazilian generators: the cable's build year."""
    if "start_year" in cfg:
        return int(cfg["start_year"])
    cable = config.get("brazil_cable") or {}
    if "build_year" in cable:
        return int(cable["build_year"])
    return int(yaml.safe_load(CABLE_PARAMETERS.read_text())["build_year"])


def add_bus(n, name: str) -> None:
    if name in n.buses.index:
        return
    n.add("Bus", name, carrier="AC", x=NATAL[0], y=NATAL[1], country="BR", v_nom=380.0)
    logger.info(f"Brazil supply: added bus {name!r}")


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    missing = [p for p in (POTENTIAL, PROFILES) if not p.is_file()]
    if missing:
        raise FileNotFoundError(
            f"Brazil supply: {', '.join(str(p.relative_to(ROOT)) for p in missing)} "
            "missing. Run: pixi run python workshop/brazil/build_rn_potential.py"
        )
    potential = pd.read_csv(POTENTIAL).rename(columns={"class": "resource_class"})
    profiles = pd.read_csv(PROFILES, index_col="timestamp_utc", parse_dates=True)
    profiles.index = profiles.index.tz_localize(None)  # model snapshots are naive UTC
    return potential, profiles


def aggregate_to_snapshots(profiles: pd.DataFrame, snapshots: pd.DatetimeIndex):
    """Hourly profiles to the model's (aggregated) snapshots, as
    adjust_renewable_profiles in scripts/add_brownfield.py does."""
    snapshotmap = (
        pd.Series(profiles.index, index=profiles.index)
        .where(lambda s: s.isin(snapshots), pd.NA)
        .ffill()
    )
    out = profiles.groupby(snapshotmap).mean().reindex(snapshots)
    if out.isna().any().any():
        raise ValueError("Brazil supply: profiles do not cover the model snapshots")
    return out


def add_brazil_supply(n, config: dict, horizon: int, costs: pd.DataFrame) -> None:
    cfg = config.get("brazil_supply") or {}
    if not cfg.get("enable", False):
        return

    bus = cfg.get("bus", DEFAULT_BUS)
    add_bus(n, bus)

    first = start_year(config, cfg)
    frozen = (
        horizon == int(config["planning_horizons"][0])
        and (config.get("existing_capacities") or {}).get("freeze_first_horizon", False)
    )
    if horizon < first or frozen:
        logger.info(f"Brazil supply: no new generators in {horizon} (start {first})")
        return
    if not (config.get("brazil_cable") or {}).get("enable", False):
        logger.warning("Brazil supply: brazil_cable is off, the supply has no outlet")

    potential, profiles = load_inputs()
    p_max_pu = aggregate_to_snapshots(profiles, n.snapshots)
    carriers = cfg.get("carriers", list(TECHNOLOGIES))
    length_factor = float(config["lines"]["length_factor"])
    line_cost = costs.at["HVAC overhead", "capital_cost"]  # EUR/MW/km/a
    colors = (config.get("plotting") or {}).get("tech_colors", {})

    for row in potential.itertuples():
        if row.carrier not in carriers:
            continue
        tech = TECHNOLOGIES[row.carrier]
        carrier = f"Brazil {row.carrier}"
        base = f"{bus} {row.carrier} {row.resource_class}"
        column = (
            f"{row.carrier} class {row.resource_class}"
            if row.carrier == "onwind"
            else row.carrier
        )
        if carrier not in n.carriers.index:
            n.add(
                "Carrier", carrier, nice_name=carrier, color=colors.get(tech, "")
            )

        connection = 0.0
        if cfg.get("connection_cost", True):
            connection = row.distance_to_converter_km * length_factor * line_cost

        built = n.generators.loc[
            n.generators.index.str.startswith(base + "-")
            & ~n.generators.p_nom_extendable,
            "p_nom",
        ].sum()
        p_nom_max = max(row.p_nom_max_mw - built, 0.0)

        name = f"{base}-{horizon}"
        n.add(
            "Generator",
            name,
            bus=bus,
            carrier=carrier,
            p_nom_extendable=True,
            p_nom_max=p_nom_max,
            capital_cost=costs.at[tech, "capital_cost"] + connection,
            marginal_cost=costs.at[tech, "marginal_cost"],
            lifetime=costs.at[tech, "lifetime"],
            build_year=horizon,
            p_max_pu=p_max_pu[column].clip(lower=0.0, upper=1.0).values,
        )
        logger.info(
            f"Brazil supply: {name}, potential {p_nom_max:,.0f} MW "
            f"(built before {built:,.0f} MW), mean CF {p_max_pu[column].mean():.3f}, "
            f"connection {connection:,.0f} EUR/MW/a"
        )

    if np.isinf(n.generators.loc[n.generators.bus == bus, "p_nom_max"]).any():
        raise ValueError("Brazil supply: unbounded potential")
