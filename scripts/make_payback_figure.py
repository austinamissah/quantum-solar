"""Web figure: the payback conclusion, which is the answer the project exists for.

Everything else here measures something. This one answers the question a person
actually asks: does the battery pay for itself? It did not have a figure, only a
table in `docs/results/capacity-rate-sensitivity.md`.

The figure has to make one point with no caption: **the conclusion does not depend
on the assumption you find plausible.** The export credit is the one input a reader
is most likely to argue with, since it is jurisdiction-specific and cannot be
verified from the committed snapshot, so it is swept from full-retail net metering
(1.0) down to near avoided cost (0.10). Payback clears the warranty line at every
point on that sweep. There is no value of the disputed input that rescues it.

The second thing on the plot is the counterintuitive one, and it is why a bracket
exists rather than a point estimate: **the pessimistic end is the shorter payback.**
A worse export credit makes exported solar worth less, which gives the battery
self-consumption value on top of arbitrage, so the battery leg gets *better* as the
solar leg gets worse. The two legs move in opposite directions, which is exactly why
this repo never sums them.

NUMBERS COME FROM THE COMMITTED STUDY, not from this file. Everything is read out of
`docs/results/capacity_rate_sensitivity.json` (`annual.by_export_ratio`), which
`scripts/battery_sizing_study.py` generates. Three gates, and the script refuses to
draw on any of them:

  * every payback figure must equal installed cost / battery savings, recomputed
    here, so a transcription error in the study would surface rather than be drawn;
  * `cheapest_within_warranty` must be null at every ratio, because the figure
    asserts that nothing clears the warranty and that field is where the study says
    so;
  * the regime must still be the 0.90 round trip the headline uses.

Run:  python scripts/make_payback_figure.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "docs" / "results" / "capacity_rate_sensitivity.json"
OUT = ROOT / "docs" / "figures" / "web" / "payback.png"

INSTALL = 11500          # the README's midpoint install cost
CHEAPEST = 5000          # the cheapest install the study prices, used as a check
EXPECTED_ROUND_TRIP = 0.90

INK = "#2F4B7C"
ACCENT = "#E45756"
BAND = "#DCE7F1"


def load_series():
    """Payback years against export credit, read and re-checked from the study."""
    annual = json.loads(STUDY.read_text())["annual"]

    if annual["round_trip_efficiency"] != EXPECTED_ROUND_TRIP:
        raise SystemExit(
            f"REFUSING TO DRAW: the study is at a "
            f"{annual['round_trip_efficiency']} round trip, but this figure is "
            f"labeled for {EXPECTED_ROUND_TRIP}."
        )

    ratios, years, savings = [], [], []
    for row in annual["by_export_ratio"]:
        payback = row["payback_years"][str(INSTALL)]
        recomputed = INSTALL / row["battery_savings"]
        if abs(payback - recomputed) > 0.05:
            raise SystemExit(
                f"REFUSING TO DRAW: at export ratio {row['export_ratio']} the study "
                f"records {payback} years, but ${INSTALL:,} / "
                f"${row['battery_savings']}/yr is {recomputed:.2f}. The study is "
                f"internally inconsistent; fix it before drawing it."
            )
        if row["cheapest_within_warranty"] is not None:
            raise SystemExit(
                f"REFUSING TO DRAW: at export ratio {row['export_ratio']} the study "
                f"now reports an install that pays back within warranty "
                f"({row['cheapest_within_warranty']}). This figure asserts that none "
                f"does; the conclusion has changed."
            )
        ratios.append(row["export_ratio"])
        years.append(payback)
        savings.append(row["battery_savings"])

    cheapest = [row["payback_years"][str(CHEAPEST)] for row in annual["by_export_ratio"]]
    return (np.array(ratios), np.array(years), np.array(savings),
            np.array(cheapest), int(annual["warranty_years"]))


def main() -> None:
    ratios, years, savings, cheapest, warranty = load_series()
    lo, hi = float(years.min()), float(years.max())
    x = np.arange(len(ratios))

    last = len(ratios) - 1
    fig, ax = plt.subplots(figsize=(11.4, 7.0))

    # The bracket, drawn as the band every assumption lands inside. Labeled high
    # in the band: the bars' own value labels sit just above each bar, and the
    # rightmost of those lands inside the band.
    ax.axhspan(lo, hi, color=BAND, zorder=0)
    ax.text(last + 0.32, hi - 0.55, f"the whole bracket: [{lo}, {hi}] years",
            ha="right", va="center", fontsize=10.5, color="#2A6099")

    ax.bar(x, years, width=0.62, color=INK, zorder=3)
    for xi, yi in zip(x, years):
        ax.text(xi, yi + 0.7, f"{yi:.1f}", ha="center", fontsize=11,
                weight="bold", color=INK)

    # The line the bars have to beat, and do not. Both labels live in the left
    # margin: every region above the line and inside the axes carries a bar.
    ax.axhline(warranty, color=ACCENT, lw=2.2, zorder=4)
    ax.text(-1.12, warranty + 0.9, f"~{warranty}-year\nwarranty", color=ACCENT,
            fontsize=11, weight="bold", va="bottom", ha="left")
    ax.text(-1.12, lo - 3.0,
            f"the shortest\npayback is\n{lo / warranty:.1f}x this",
            color=ACCENT, fontsize=9.5, va="center", ha="left")

    # The counterintuitive direction, which is why a bracket exists at all.
    ax.annotate(
        "", xy=(last, hi + 4.2), xytext=(0, hi + 4.2),
        arrowprops=dict(arrowstyle="->", color="0.4", lw=1.6),
    )
    ax.text(last / 2, hi + 5.0, "worse export credit, shorter payback",
            ha="center", va="bottom", fontsize=9.5, color="0.4", style="italic")
    ax.text(last / 2, hi + 11.4,
            "The pessimistic end is the SHORTER payback.\n"
            "A worse export credit makes exported solar worth less, so the battery\n"
            "earns self-consumption value on top of arbitrage. The solar leg and the\n"
            "battery leg move in opposite directions, which is why this is a bracket.",
            ha="center", va="center", fontsize=10, color="0.3")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{r:g}" for r in ratios], fontsize=11)
    ax.set_xlim(-1.15, last + 0.55)
    ax.set_ylim(0, hi + 15.5)
    ax.set_xlabel("export credit as a fraction of the retail import price",
                  fontsize=11, labelpad=34)
    ax.set_ylabel(f"years to pay back an ${INSTALL:,} install", fontsize=11)
    ax.text(0, -0.055, "full retail\n(net metering)",
            transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=9, color="0.45")
    ax.text(last, -0.055, "near\navoided cost",
            transform=ax.get_xaxis_transform(), ha="center", va="top",
            fontsize=9, color="0.45")
    ax.grid(axis="y", alpha=0.25, lw=0.7)
    ax.set_axisbelow(True)

    fig.suptitle("It does not pay back, whatever you assume about the export credit",
                 fontsize=15, y=0.975)
    ax.set_title(f"10 kWh battery at 2 kW, {EXPECTED_ROUND_TRIP:g} AC round trip, "
                 f"Xcel RE-TOU. Arbitrage alone, which is all this model prices.",
                 fontsize=10.5, color="0.4", pad=12)
    fig.tight_layout(rect=(0, 0.165, 1, 0.945))

    fig.text(
        0.5, 0.088,
        f"The cheapest install the study prices, ${CHEAPEST:,}, misses the warranty "
        f"too: {cheapest.min():.1f} to {cheapest.max():.1f} years across the same "
        f"sweep. Batteries are also bought for backup and resilience,\nwhich this "
        f"model does not price and which may well justify a purchase. The savings "
        f"pitch is what does not survive the arithmetic.",
        ha="center", va="center", fontsize=10, color="0.3",
    )
    fig.text(0.5, 0.024,
             "Exact 365-day dynamic-programming solve per point; numbers read from "
             "docs/results/capacity_rate_sensitivity.json.",
             ha="center", fontsize=10, color="0.35")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    for r, y, s in zip(ratios, years, savings):
        print(f"  export {r:>4.2f} x retail   ${s:>7.2f}/yr   {y:>5.1f} years"
              f"   [recomputed {INSTALL / s:.2f}]")
    print(f"  bracket [{lo}, {hi}] years against a {warranty}-year warranty; "
          f"nothing clears it")
    print(f"  cheapest install (${CHEAPEST:,}): {cheapest.min():.1f} to "
          f"{cheapest.max():.1f} years, also never clears")


if __name__ == "__main__":
    main()
