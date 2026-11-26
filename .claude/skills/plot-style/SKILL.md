---
name: plot-style
description: The default style for every chart in this workshop - matplotlib figures, plotly or PyPSA plots, and charts drawn in HTML/SVG. Libre Franklin, no chart frame, quiet y grid, flat fills, Okabe-Ito colours with one fixed colour per technology group. Load it whenever you write or change plotting code or make a figure, unless the person asks for another look.
---

<!--
SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>

SPDX-License-Identifier: CC-BY-4.0
-->

# Workshop plot style

Every figure the group makes uses this style, so the four roles' figures fit together in the final
presentation. The code is in `workshop/plotstyle/`:

| File | Role |
|---|---|
| `study.mplstyle` | the rcParams (by Iegor Riepin, MIT): fonts, colours, grid, ticks, spines, Okabe-Ito cycle |
| `studystyle.py` | `use()`, colour constants, carrier and group colours, small helpers |
| `fonts/` | Libre Franklin (SIL OFL 1.1), registered by `use()`, no system install needed |

PyPSA-Eur's own plotting rules (`scripts/plot_*.py`) keep their look; restyle them only when asked.

## Use

```python
import sys
from pathlib import Path
import matplotlib.pyplot as plt
# works from scripts, notebooks and Snakemake rules anywhere below the repo root
sys.path.insert(0, str(next(p for p in [Path.cwd(), *Path.cwd().parents]
                            if (p / "workshop/plotstyle").is_dir()) / "workshop/plotstyle"))
import studystyle as st

st.use()
gen = n.statistics.supply(bus_carrier="AC", groupby="carrier").droplevel(0) / 1e6   # TWh
mix = st.by_group(gen)                       # carriers -> technology groups, in stacking order
fig, ax = plt.subplots(figsize=(5.6, 3.4))
st.bars(ax, range(len(mix)), mix.values, color=[st.GROUPS[g] for g in mix.index])
ax.set_xticks(range(len(mix)), mix.index)
ax.set_title("Electricity generation in Germany, 2050, TWh", loc="left")
fig.savefig("generation.pdf")
```

For PyPSA's built-in plots (`n.plot`, `n.statistics.<metric>.plot...`), call `st.set_carrier_colors(n)` first
so they draw with the same colours.

## The rules

1. **One sans typeface.** Libre Franklin; DejaVu Sans only covers missing glyphs. Text `#222222`, axis labels
   `#333333`, tick labels `#444444` (x) / `#666666` (y), faint notes `#aaaaaa`.
2. **No chart frame, quiet grid.** Only the bottom spine (0.8 pt, `#222222`); y grid `#dcdcdc` 0.5 pt; no tick
   marks.
3. **Flat fills, no outlines.** Bars and areas carry no edge; stacked segments are separated by a thin white
   seam (`st.stacked_bars`). Hatching (`////`) marks a subset inside a group, e.g. floating offshore wind
   inside offshore wind.
4. **Fixed colours per technology group** (`st.GROUPS`, stacking order bottom to top): nuclear pink
   `#CC79A7`, lignite `#6e6e6e`, coal `#222222`, gas `#9e9e9e` (OCGT `#cfcfcf` where gas is split), oil
   `#E69F00`, biomass `#009E73`, hydro `#0072B2`, offshore wind `#1B3F73`, onshore wind `#56B4E9`, solar
   `#F0E442`, storage `#7E6BB0`, **Brazil cable `#D55E00`**, other `#d4d4d4`. A colour always means the same
   technology, in every chart and every role. Never invent a new colour for a carrier: map it with
   `st.group()` / `st.color()`. Give the Brazil cable a carrier whose name contains "Brazil" so it gets its
   colour. A reference or "without the cable" series is neutral grey `#c4c4c4` (`st.NEUTRAL`).
5. **Plot by group, not by carrier.** `st.by_group()` folds PyPSA-Eur's ~25 carriers (codes or the nice names `n.statistics` returns) into the
   groups above and drops AC/DC grid flows; a
   chart shows at most about eight. Split a group into carriers only when that split is the point of the chart.
6. **Labels close to the data**, in ink (`#222222`), never in the series colour. Values above bars and at line
   points in 7.5 pt; direct labels at line ends instead of a legend where there is room (nudge them apart when two
   lines end close together); legends are frameless
   with flat squares (`st.legend_squares`).
7. **Titles** sit top left, bold, and name quantity, place, year and unit ("Electricity generation in Germany,
   2050, TWh"), so the y axis needs no label. Units: GW and TWh for the system, EUR/MWh for prices,
   EUR/t for CO2, Mt for emissions, billion EUR for costs.
8. **One y axis.** Two quantities with different units go in two panels, never on twin axes.
9. **Maps** keep their colormaps; land without data `#eeeeee`, borders and coast in `#222222` at 0.5 pt, no
   ticks or frame (`st.map_axes`), and a slim horizontal colour bar whose label (quantity and unit) sits on top
   (`st.colorbar`).
10. **Layout and output.** The style turns constrained layout on; a figure laid out by hand needs
   `plt.figure(layout="none")`. Default size 5.6 x 3.4 in. Save PDF for slides and PNG at 300 dpi for
   chats and READMEs.

## Helpers (`studystyle.py`)

| Helper | Does |
|---|---|
| `use()` | registers the fonts and applies the style sheet |
| `group(carrier)`, `color(carrier)` | technology group and colour of any PyPSA-Eur carrier |
| `by_group(df, axis=0)` | sums a carrier-indexed Series/DataFrame into groups, in stacking order |
| `set_carrier_colors(n)` | writes the colours into `n.carriers.color` for PyPSA's own plots |
| `bars(ax, x, h, color, labels=True)` | flat bars with value labels |
| `stacked_bars(ax, x, parts)` | stacked bars from a DataFrame (columns = groups), white seams, totals on top |
| `line(ax, x, y, color, label=None, values=False)` | line with round markers, end label, optional point values |
| `legend_squares(ax, [(colour, label[, alpha]), ...])` | frameless legend of flat squares |
| `map_axes(ax)` | strips grid, ticks and spines from a map panel |
| `colorbar(fig, mappable, cax, label, ticks=None)` | slim horizontal colour bar with the label on top |

## Plotly, HTML and SVG

Same tokens: font stack `"Libre Franklin", "DejaVu Sans", "Helvetica Neue", Arial, sans-serif` (Google Fonts,
weights 400 / 600 / 700), text `#222222`, labels `#444444`, ticks `#666666`, grid `#dcdcdc` at 0.6 px, bottom
axis line `#222222` at 0.9 px, white background, flat bars, the group colours above. In plotly:
`template="simple_white"`, then set `font_family`, the colours and `yaxis_showgrid=True` with that grid colour.
