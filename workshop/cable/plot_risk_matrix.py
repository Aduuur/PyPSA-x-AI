# SPDX-FileCopyrightText: Contributors to PyPSA-Eur <https://github.com/pypsa/pypsa-eur>
#
# SPDX-License-Identifier: MIT
"""
Risk matrix of the Brazil cable from workshop/cable/risk_register.csv.

Writes results/cable/risk_matrix.png/.pdf and workshop/cable/results/risk_matrix.svg.

    pixi run python workshop/cable/plot_risk_matrix.py
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "workshop/plotstyle").is_dir())
sys.path.insert(0, str(ROOT / "workshop/plotstyle"))
import studystyle as st  # noqa: E402

OUT = ROOT / "results/cable"
SHARED = ROOT / "workshop/cable/results"


def main():
    reg = pd.read_csv(ROOT / "workshop/cable/risk_register.csv")
    st.use()
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    # background: score = likelihood x impact, neutral greys, the highest band in the cable colour
    for li in range(1, 6):
        for im in range(1, 6):
            score = li * im
            c, a = ((st.GROUPS["Brazil cable"], 0.18) if score >= 15 else
                    ("#9e9e9e", 0.18) if score >= 8 else (st.LAND, 1))
            ax.add_patch(plt.Rectangle((li - 0.5, im - 0.5), 1, 1, color=c, alpha=a, lw=0))
    # place ids in their cell, spread when several share one
    for (li, im), g in reg.groupby(["likelihood", "impact"]):
        n = len(g)
        cols = min(n, 3)
        for k, rid in enumerate(g.id):
            dx = ((k % cols) - (cols - 1) / 2) * 0.28
            dy = -((k // cols) - (np.ceil(n / cols) - 1) / 2) * 0.22
            ax.text(li + dx, im + dy, rid, ha="center", va="center", fontsize=7.5, color=st.TEXT)
    ax.set_xlim(0.5, 5.5)
    ax.set_ylim(0.5, 5.5)
    ax.set_xticks(range(1, 6), ["rare", "unlikely", "possible", "likely", "almost\ncertain"])
    ax.set_yticks(range(1, 6), ["minor", "moderate", "serious", "major", "critical"])
    ax.grid(False)
    ax.set_xlabel("Likelihood")
    ax.set_title("Risks of the Brazil cable Natal-Wilhelmshaven, likelihood and impact", loc="left")
    st.legend_squares(ax, [(st.GROUPS["Brazil cable"], "high (score 15 or more)", 0.35),
                           ("#9e9e9e", "medium (8-14)", 0.35)],
                      loc="lower right", fontsize=7)
    fig.text(0.01, -0.01, "Ids refer to workshop/cable/RISKS.md. Role 1 judgement, see sources there.",
             fontsize=6.5, color=st.FAINT)
    OUT.mkdir(parents=True, exist_ok=True)
    SHARED.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "risk_matrix.png", dpi=200, bbox_inches="tight")
    fig.savefig(OUT / "risk_matrix.pdf", bbox_inches="tight")
    fig.savefig(SHARED / "risk_matrix.svg", bbox_inches="tight")


if __name__ == "__main__":
    main()
