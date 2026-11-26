# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""Study plot style: the default look of every workshop figure (study.mplstyle by Iegor Riepin).

From pypsalabs/catalyst-project, with colours for PyPSA-Eur's carriers added. One sans typeface (Libre
Franklin, DejaVu Sans as fallback), no chart frame, a quiet y grid, flat fills without outlines, Okabe-Ito
colours.

    import sys
    from pathlib import Path
    sys.path.insert(0, str(next(p for p in [Path.cwd(), *Path.cwd().parents]
                                if (p / "workshop/plotstyle").is_dir()) / "workshop/plotstyle"))
    import studystyle as st

    st.use()
    fig, ax = plt.subplots()
    st.bars(ax, years, values, color=st.GROUPS["Solar"])
    ax.set_title("Solar capacity in Germany, GW", loc="left")

The style switches constrained layout on; a figure laid out by hand needs plt.figure(layout="none").
"""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Patch

STYLE = Path(__file__).with_name("study.mplstyle")
FONTS = Path(__file__).with_name("fonts")  # Libre Franklin static .ttf (SIL OFL 1.1, OFL.txt), registered by use()

TEXT, LABEL, TICK, GRID, FAINT = "#222222", "#333333", "#666666", "#dcdcdc", "#aaaaaa"
NEUTRAL, LAND = "#c4c4c4", "#eeeeee"  # reference / "without" series; land without data on maps
BLACK, ORANGE, SKY, GREEN, YELLOW, BLUE, VERMILLION, PINK = OKABE_ITO = [
    "#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7"]
NAVY = "#1B3F73"     # offshore wind: not Okabe-Ito, checked against hydro and onshore wind for colour-blind separation
STORAGE = "#7E6BB0"  # not Okabe-Ito, as in the catalyst style
TINT = 0.42          # opacity of the lighter half of a two-part bar

# Technology groups in stacking order (bottom to top). Plot at this level by default: one colour per group.
GROUPS = {
    "Nuclear": PINK,
    "Lignite": "#6e6e6e",
    "Coal": TEXT,
    "Gas": "#9e9e9e",
    "Oil": ORANGE,
    "Biomass": GREEN,
    "Hydro": BLUE,
    "Offshore wind": NAVY,
    "Onshore wind": SKY,
    "Solar": YELLOW,
    "Storage": STORAGE,
    "Brazil cable": VERMILLION,  # the study's subject: the only red-orange in any chart
    "Other": "#d4d4d4",
}

# PyPSA-Eur carrier -> group. Carriers not listed fall back by prefix (see group()).
CARRIER_GROUP = {
    "nuclear": "Nuclear", "lignite": "Lignite", "coal": "Coal",
    "CCGT": "Gas", "OCGT": "Gas", "gas": "Gas", "oil": "Oil",
    "biomass": "Biomass", "waste": "Biomass",
    "ror": "Hydro", "hydro": "Hydro",
    "onwind": "Onshore wind", "solar": "Solar", "solar-hsat": "Solar",
    "PHS": "Storage", "battery": "Storage", "H2": "Storage",
    "battery charger": "Storage", "battery discharger": "Storage",
    "H2 Electrolysis": "Storage", "H2 Fuel Cell": "Storage",
    "geothermal": "Other",
    # nice names, which n.statistics returns in place of the carrier codes
    "Combined-Cycle Gas": "Gas", "Open-Cycle Gas": "Gas",
    "Reservoir & Dam": "Hydro", "Run of River": "Hydro", "Pumped Hydro Storage": "Storage",
}
# Carrier-level colours where a split inside a group is shown: open-cycle gas lighter than combined-cycle.
CARRIER_COLOR = {"OCGT": "#cfcfcf", "Open-Cycle Gas": "#cfcfcf", "AC": "#555555", "DC": "#555555"}
_LOWER = {k.lower(): v for k, v in {**CARRIER_GROUP, **{g: g for g in GROUPS}}.items()}


def group(carrier):
    """The technology group of a PyPSA-Eur carrier code or nice name ("onwind" and "Onshore Wind" alike)."""
    lc = str(carrier).lower()
    if "brazil" in lc:
        return "Brazil cable"
    if lc in _LOWER:
        return _LOWER[lc]
    for prefix, g in [("offwind", "Offshore wind"), ("offshore wind", "Offshore wind"),
                      ("onwind", "Onshore wind"), ("onshore wind", "Onshore wind"), ("solar", "Solar"),
                      ("battery", "Storage"), ("h2", "Storage"), ("hydrogen", "Storage"), ("hydro", "Hydro"),
                      ("gas", "Gas")]:
        if lc.startswith(prefix):
            return g
    return "Other"


def color(carrier):
    """Colour of a carrier: its own if it has one, else its group's."""
    return CARRIER_COLOR.get(str(carrier), GROUPS[group(carrier)])


def set_carrier_colors(n):
    """Write these colours into n.carriers.color, so PyPSA's own plots (n.plot, n.statistics...plot) use them."""
    n.carriers["color"] = [color(c) for c in n.carriers.index]
    return n


TRANSMISSION = {"AC", "DC"}  # grid flows, not generation: by_group drops them (the Brazil cable is kept)


def by_group(df, axis=0):
    """Sum a carrier-indexed Series/DataFrame into groups, in stacking order (empty groups and AC/DC lines dropped)."""
    if axis == 1:
        return by_group(df.T).T
    df = df[[str(c) not in TRANSMISSION for c in df.index]]
    out = df.groupby(group).sum()
    return out.loc[[g for g in GROUPS if g in out.index]]


def use():
    if FONTS.is_dir():
        for f in FONTS.glob("*.ttf"):
            font_manager.fontManager.addfont(str(f))
    plt.style.use(STYLE)


def bars(ax, x, height, color, width=0.62, labels=True, fmt="{:,.0f}", **kw):
    """Flat bars without outline; optional value labels above."""
    out = ax.bar(x, height, width=width, color=color, linewidth=0, zorder=2, **kw)
    if labels:
        for rect, v in zip(out, height):
            ax.annotate(fmt.format(v), (rect.get_x() + rect.get_width() / 2, rect.get_y() + rect.get_height()),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=7.5, color=TEXT)
    return out


def stacked_bars(ax, x, parts, width=0.62, totals=True, fmt="{:,.0f}"):
    """Stacked bars from a DataFrame (rows = x, columns = groups or carriers), thin white seams, totals on top."""
    bottom = 0
    for col in parts.columns:
        ax.bar(x, parts[col].values, width=width, bottom=bottom, color=color(col), edgecolor="white",
               linewidth=0.6, zorder=2, label=col)
        bottom = bottom + parts[col].values
    if totals:
        for xi, t in zip(x, bottom):
            ax.annotate(fmt.format(t), (xi, t), xytext=(0, 3), textcoords="offset points", ha="center",
                        va="bottom", fontsize=7.5, color=TEXT)


def line(ax, x, y, color, label=None, values=False, fmt="{:,.0f}", **kw):
    """Plain line with round markers; `label` is written after the last point, `values` labels every point."""
    x, y = list(x), list(y)
    out = ax.plot(x, y, color=color, lw=1.4, marker="o", ms=3.4, mew=0, zorder=3, **kw)
    if values:
        for xi, yi in zip(x, y):
            ax.annotate(fmt.format(yi), (xi, yi), xytext=(0, 5), textcoords="offset points", ha="center",
                        fontsize=7.5, color=TEXT)
    if label:
        ax.annotate(label, (x[-1], y[-1]), xytext=(7, 0), textcoords="offset points", va="center", fontsize=7.5,
                    color=TEXT)
    return out


def legend_squares(ax, items, **kw):
    """Frameless legend of flat squares: items = [(colour, label), ...] or [(colour, label, alpha), ...]."""
    handles = [Patch(facecolor=it[0], edgecolor="none", alpha=it[2] if len(it) > 2 else 1, label=it[1])
               for it in items]
    kw = dict(dict(loc="upper left", handlelength=0.9, handleheight=0.9, handletextpad=0.5, borderaxespad=0), **kw)
    return ax.legend(handles=handles, **kw)


def map_axes(ax):
    """A map panel: no grid, ticks or spines."""
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def colorbar(fig, mappable, cax, label, ticks=None, fmt=None):
    """Slim horizontal colour bar with its label (quantity and unit) on top."""
    cb = fig.colorbar(mappable, cax=cax, orientation="horizontal", ticks=ticks, format=fmt)
    cb.outline.set_edgecolor(TEXT)
    cb.outline.set_linewidth(0.5)
    cax.tick_params(length=0, pad=3, labelsize=7.5, labelcolor=TICK)
    cax.xaxis.set_label_position("top")
    cax.set_xlabel(label, fontsize=7.5, color=LABEL, labelpad=4)
    return cb
