# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Cost of capital per project asset, read at runtime from the confidential
financing term sheet (``workshop/inputs/financing_term_sheet.md``).

No value from the term sheet is written into this file, into shared configs or
printed by default. The derived figures go to ``workshop/private/`` only
(git-ignored); see "Confidential data" in AGENTS.md.

Use from code (roles 1 and 2 read their asset's figures at runtime)::

    from financing import load
    fin = load()                      # dict per asset: "cable", "brazil", "germany"
    fin["cable"]["wacc"]              # after-tax WACC, fraction
    fin["cable"]["idc_factor"]        # multiply overnight investment by this
    fin["brazil_fx_brl_per_eur"]

Or write the private files::

    pixi run python workshop/economics/financing.py
    # -> workshop/private/financing.yaml   (all derived figures)

Definitions
    cost of debt   = base rate + margin
    WACC (pre-tax) = g * cost of debt + (1 - g) * equity return
    WACC (after tax, used for annuities)
                   = g * cost of debt * (1 - tax rate) + (1 - g) * equity return
    IDC factor     = ((1 + WACC)^T - 1) / (WACC * T), spend spread evenly over
                     the T construction years and interest capitalised to
                     commissioning. Applied to the overnight investment.
The equity return already contains the country risk premium (term sheet).
"""

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TERM_SHEET = ROOT / "workshop" / "inputs" / "financing_term_sheet.md"
PRIVATE = ROOT / "workshop" / "private"

# keyword in the asset name -> short key; tax and construction time follow the asset
ASSETS = {"cable": "cable", "brazil": "brazil", "german": "germany"}
TAX_KEY = {"cable": "cable", "brazil": "brazil", "germany": "germany"}
IDC_KEY = {"cable": "cable", "brazil": "generation", "germany": "generation"}


def pct(s):
    return float(s.strip().rstrip("%")) / 100


def num(s):
    return float(s.replace(",", "").strip())


def parse_table(text):
    """The financing table: one row per asset, columns by header name."""
    lines = [ln for ln in text.splitlines() if ln.strip().startswith("|")]
    if len(lines) < 3:
        raise ValueError("financing table not found")
    head = [h.strip().lower() for h in lines[0].strip("|").split("|")]
    rows = {}
    for ln in lines[2:]:
        cells = [c.strip() for c in ln.strip("|").split("|")]
        row = dict(zip(head, cells))
        name = row[head[0]].lower()
        key = next((k for kw, k in ASSETS.items() if kw in name), None)
        if key is None:
            continue

        def col(word):
            return next(v for h, v in row.items() if word in h)

        rows[key] = {
            "gearing": pct(col("gearing")),
            "base_rate": pct(col("base rate")),
            "margin": num(col("margin")) / 1e4,  # bps
            "tenor_years": num(col("tenor")),
            "min_cover_ratio": num(col("cover")),
            "equity_return": pct(col("equity return")),
            "country_risk_premium": pct(col("country risk")),
        }
    missing = set(ASSETS.values()) - set(rows)
    if missing:
        raise ValueError(f"assets missing in the financing table: {sorted(missing)}")
    return rows


def parse_tax(text):
    """{'germany': t, 'cable': t, 'brazil': t} from the interest-shield line."""
    line = next(ln for ln in text.splitlines() if "tax rate" in ln.lower())
    out = {}
    for m in re.finditer(r"([\d.]+)%\s+in\s+([^,.]+(?:\.\d[^,.]*)?)", line):
        rate, where = pct(m.group(1)), m.group(2).lower()
        if "germany" in where:
            out["germany"] = rate
        if "cable" in where:
            out["cable"] = rate
        if "brazil" in where:
            out["brazil"] = rate
    if set(out) != {"germany", "cable", "brazil"}:
        raise ValueError("could not read the tax rates")
    return out


def parse_idc(text):
    """Construction years with capitalised interest: {'generation': T, 'cable': T}."""
    line = next(ln for ln in text.splitlines() if "construction" in ln.lower())
    out = {}
    for m in re.finditer(r"(\d+)\s+years?\s+for\s+(?:the\s+)?(\w+)", line):
        out[m.group(2).lower()] = int(m.group(1))
    if not {"generation", "cable"} <= set(out):
        raise ValueError("could not read the construction periods")
    return out


def parse_fx(text):
    line = next(ln for ln in text.splitlines() if "exchange rate" in ln.lower())
    m = re.search(r"([\d.]+)\s*BRL per EUR", line)
    h = re.search(r"hedged for (\d+) years at ([\d.]+)%", line)
    if not m:
        raise ValueError("could not read the exchange rate")
    return num(m.group(1)), (int(h.group(1)), pct(h.group(2))) if h else (None, None)


def idc_factor(rate, years):
    if years <= 0 or rate == 0:
        return 1.0
    return ((1 + rate) ** years - 1) / (rate * years)


def annuity(rate, lifetime):
    return rate / (1 - (1 + rate) ** -lifetime) if rate else 1 / lifetime


def load(path=TERM_SHEET):
    """Derived financing figures per asset. Reads the term sheet at runtime."""
    text = Path(path).read_text()
    table, tax, idc = parse_table(text), parse_tax(text), parse_idc(text)
    fx, (hedge_years, hedge_cost) = parse_fx(text)
    out = {}
    for key, r in table.items():
        kd = r["base_rate"] + r["margin"]
        g, ke, t = r["gearing"], r["equity_return"], tax[TAX_KEY[key]]
        wacc = g * kd * (1 - t) + (1 - g) * ke
        T = idc[IDC_KEY[key]]
        out[key] = {
            **r,
            "cost_of_debt": kd,
            "tax_rate": t,
            "wacc_pre_tax": g * kd + (1 - g) * ke,
            "wacc": wacc,
            "construction_years": T,
            "idc_factor": idc_factor(wacc, T),
        }
    out["brazil_fx_brl_per_eur"] = fx
    out["brazil_fx_hedge_years"] = hedge_years
    out["brazil_fx_hedge_cost"] = hedge_cost
    return out


def write_private(fin, out_dir=PRIVATE):
    import yaml

    out_dir.mkdir(parents=True, exist_ok=True)
    clean = {k: ({kk: float(vv) for kk, vv in v.items()} if isinstance(v, dict) else v)
             for k, v in fin.items()}
    path = out_dir / "financing.yaml"
    path.write_text(
        "# DERIVED FROM CONFIDENTIAL DATA (workshop/inputs/financing_term_sheet.md).\n"
        "# Local only: never commit, copy or quote. Regenerate with\n"
        "#   pixi run python workshop/economics/financing.py\n"
        + yaml.safe_dump(clean, sort_keys=False)
    )
    return path


def check(fin):
    """Sanity checks without showing any value."""
    problems = []
    for key in ASSETS.values():
        a = fin[key]
        if not 0 < a["wacc"] < 0.25:
            problems.append(f"{key}: WACC outside 0-25%")
        if not a["wacc"] < a["wacc_pre_tax"]:
            problems.append(f"{key}: after-tax WACC not below pre-tax WACC")
        if not 1 <= a["idc_factor"] < 1.5:
            problems.append(f"{key}: IDC factor outside 1-1.5")
        if not 0 < a["gearing"] < 1:
            problems.append(f"{key}: gearing outside 0-1")
    return problems


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--show", action="store_true",
                   help="print the derived figures (local terminal only; never paste them anywhere)")
    a = p.parse_args()
    if not TERM_SHEET.is_file():
        sys.exit(f"{TERM_SHEET.relative_to(ROOT)} not found: it is local to each workspace")
    fin = load()
    problems = check(fin)
    path = write_private(fin)
    print(f"wrote {path.relative_to(ROOT)} (git-ignored)")
    print("checks: " + ("all passed" if not problems else "; ".join(problems)))
    if a.show:
        for k, v in fin.items():
            print(k, v)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
