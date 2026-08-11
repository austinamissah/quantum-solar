"""Web figure: the sizing rule, which is the one result a buyer can act on.

`docs/results/capacity-rate-sensitivity.md` derives it and verifies it at 56 points,
but it had no picture, and it is the finding most likely to change what somebody
actually purchases.

    saving = min(capacity_kWh, rate_kW x peak_hours) x price_spread

Two panels sharing an axis of annual battery savings. Sweeping **capacity** at a
fixed 2 kW inverter, the curve climbs and then goes flat at 8 kWh: past that, the
inverter cannot push the extra energy out inside the peak window, so it is never
discharged at the high price and earns nothing. Sweeping the **rate** at a fixed
10 kWh pack, it climbs and goes flat at 2.5 kW, where 2.5 x 4 hours finally equals
the pack and the capacity becomes the binding term instead.

The point, which is why the figure exists: **vendors quote kWh, and kWh is the wrong
number to buy on.** The binding quantity is the smaller of the two terms, and for
most installed systems it is the inverter, not the pack.

One constant runs through both panels and is drawn on them. Below the bind the
annual saving is exactly linear in delivered peak energy, at $56.9646/yr per kWh/day
of peak-window throughput, which is nothing more than the year's price spreads
summed. That single number generates four separate headline figures in this repo:
the 2 -> 2.5 kW upgrade (+$113.93), the 10 -> 20 kWh upgrade ($0.00), and the two
encoding steps in `slack-free-encoding.md` (cp5band -> cp5 at -$113.93,
cp5 -> cp3 at -$227.86). Every one is a whole number of 2 kWh/day steps.

REGIME. Drawn LOSSLESS, because that is the regime the $56.9646 constant and the
encoding-study figures live in. At the 0.90 round trip the multiplier scales down
(to $50.5346) but **the knee does not move**: it is 8 kWh either way, which the
script asserts rather than claims. Losses change how much each kWh/day is worth,
not which kWh/day are reachable.

NUMBERS ARE COMPUTED BY THE STUDY'S OWN FUNCTION. The sweeps call
`battery_sizing_study.annual_savings_for`, the same code that produced the committed
`capacity_rate_sensitivity.json`, so the figure cannot drift from it. The script then
refuses to draw unless it reproduces every annual anchor that file records, in both
regimes, plus the committed knee.

Run:  python scripts/make_sizing_figure.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from battery_sizing_study import SNAP, annual_savings_for  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "docs" / "results" / "capacity_rate_sensitivity.json"
OUT = ROOT / "docs" / "figures" / "web" / "sizing.png"

PEAK_HOURS = 4                 # the RE-TOU on-peak window, 5pm to 9pm
CAPACITIES = (2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0)
RATES = (0.5, 1.0, 2.0, 2.5, 5.0)
FIXED_RATE, FIXED_CAPACITY = 2.0, 10.0
TOL = 0.01                     # the study rounds its annual figures to the cent

INK = "#2F4B7C"
ACCENT = "#E45756"
RULE = "#8FB8DC"


def useful(capacity: float, rate: float) -> float:
    """kWh/day the inverter can actually deliver inside the peak window."""
    return min(capacity, rate * PEAK_HOURS)


def sweeps():
    """Both annual sweeps, gated against every anchor the study committed."""
    snapshot = json.loads(SNAP.read_text())
    annual = json.loads(STUDY.read_text())["annual"]
    window = next(w for w in json.loads(STUDY.read_text())["windows"]
                  if w["peak_hours"] == PEAK_HOURS)

    def battery(capacity, rate, round_trip=1.0):
        return annual_savings_for(snapshot, capacity, rate, round_trip)

    by_capacity = np.array([battery(c, FIXED_RATE) for c in CAPACITIES])
    by_rate = np.array([battery(FIXED_CAPACITY, r) for r in RATES])

    # --- the committed anchors, in both regimes ---------------------------
    checks = [
        ("battery_savings_lossless", battery(FIXED_CAPACITY, FIXED_RATE),
         annual["battery_savings_lossless"]),
        ("battery_savings_2kw (0.90)", battery(FIXED_CAPACITY, 2.0, 0.90),
         annual["battery_savings_2kw"]),
        ("battery_savings_2p5kw (0.90)", battery(FIXED_CAPACITY, 2.5, 0.90),
         annual["battery_savings_2p5kw"]),
        ("rate_upgrade_gain (0.90)",
         battery(FIXED_CAPACITY, 2.5, 0.90) - battery(FIXED_CAPACITY, 2.0, 0.90),
         annual["rate_upgrade_gain"]),
        ("capacity_upgrade_gain (0.90)",
         battery(20.0, FIXED_RATE, 0.90) - battery(10.0, FIXED_RATE, 0.90),
         annual["capacity_upgrade_gain"]),
    ]
    for name, got, want in checks:
        if abs(got - want) > TOL:
            raise SystemExit(
                f"REFUSING TO DRAW: {name} recomputes to {got:.4f}, but "
                f"{STUDY.name} records {want}. The figure and the study have "
                f"diverged; fix that before drawing either."
            )

    # --- the knee, and that losses do not move it -------------------------
    ceiling = by_capacity.max()
    knee_capacity = min(c for c, s in zip(CAPACITIES, by_capacity)
                        if abs(s - ceiling) < TOL)
    if knee_capacity != window["saturation_capacity_kwh"]:
        raise SystemExit(
            f"REFUSING TO DRAW: the capacity knee computes to {knee_capacity} kWh, "
            f"but the study records {window['saturation_capacity_kwh']}."
        )
    lossy = np.array([battery(c, FIXED_RATE, 0.90) for c in CAPACITIES])
    lossy_knee = min(c for c, s in zip(CAPACITIES, lossy)
                     if abs(s - lossy.max()) < TOL)
    if lossy_knee != knee_capacity:
        raise SystemExit(
            f"REFUSING TO DRAW: the knee moves with losses ({knee_capacity} kWh "
            f"lossless vs {lossy_knee} at a 0.90 round trip). The figure says it "
            f"does not."
        )

    # --- linearity: one constant, every point below the bind --------------
    per_kwh = {round(s / useful(c, FIXED_RATE), 4)
               for c, s in zip(CAPACITIES, by_capacity)}
    per_kwh |= {round(s / useful(FIXED_CAPACITY, r), 4)
                for r, s in zip(RATES, by_rate)}
    if len(per_kwh) != 1:
        raise SystemExit(
            f"REFUSING TO DRAW: the saving is not linear in peak throughput; "
            f"saving per kWh/day takes values {sorted(per_kwh)}. The figure "
            f"states a single constant."
        )

    # The rate knee is read off its own sweep, not derived from the capacity
    # knee: they are different quantities. Capacity saturates where the inverter
    # can no longer empty the pack inside the window (rate x hours = 8 kWh);
    # rate saturates where it finally can (capacity / hours = 2.5 kW).
    knee_rate = min(r for r, s in zip(RATES, by_rate)
                    if abs(s - by_rate.max()) < TOL)
    if abs(knee_rate - FIXED_CAPACITY / PEAK_HOURS) > 1e-9:
        raise SystemExit(
            f"REFUSING TO DRAW: the rate knee measures {knee_rate} kW but the rule "
            f"puts it at capacity / peak_hours = "
            f"{FIXED_CAPACITY / PEAK_HOURS:g} kW."
        )
    return by_capacity, by_rate, knee_capacity, knee_rate, per_kwh.pop()


def main() -> None:
    by_capacity, by_rate, knee_capacity, knee_rate, constant = sweeps()
    ymax = max(by_capacity.max(), by_rate.max())

    fig, (ax_c, ax_r) = plt.subplots(1, 2, figsize=(13.2, 6.6), sharey=True)

    for ax, xs, ys, knee, fixed_label, xlabel, binds in (
        (ax_c, CAPACITIES, by_capacity, knee_capacity,
         f"inverter fixed at {FIXED_RATE:g} kW", "battery capacity (kWh)",
         "the inverter binds"),
        (ax_r, RATES, by_rate, knee_rate,
         f"pack fixed at {FIXED_CAPACITY:g} kWh", "inverter rating (kW)",
         "the pack binds"),
    ):
        xs = np.array(xs, dtype=float)
        # The rule, drawn as a line; the exact 365-day solves, drawn as points.
        dense = np.linspace(xs.min(), xs.max(), 400)
        predicted = [constant * useful(d, FIXED_RATE) if ax is ax_c
                     else constant * useful(FIXED_CAPACITY, d) for d in dense]
        ax.plot(dense, predicted, color=RULE, lw=5, solid_capstyle="round", zorder=1)
        ax.plot(xs, ys, "o", color=INK, ms=9, zorder=3)

        plateau = ys.max()
        ax.axvline(knee, color=ACCENT, ls="--", lw=1.6, zorder=2)
        ax.text(knee, plateau + ymax * 0.045,
                f"knee at {knee:g} {'kWh' if ax is ax_c else 'kW'}",
                ha="center", fontsize=11, weight="bold", color=ACCENT)
        ax.text(knee + (xs.max() - xs.min()) * 0.035, plateau * 0.42,
                f"flat past here:\n{binds}", fontsize=10, color=ACCENT, va="center")
        ax.set_xlabel(xlabel, fontsize=11)
        ax.set_title(fixed_label, fontsize=12.5)
        ax.set_ylim(0, ymax * 1.30)
        ax.grid(alpha=0.25, lw=0.7)
        ax.set_axisbelow(True)

    ax_c.set_ylabel("annual battery savings ($/yr)", fontsize=11)
    ax_c.text(2.4, ymax * 1.26,
              f"slope: ${constant:.2f}/yr per kWh/day\nof peak throughput",
              fontsize=9.5, color="#2A6099", va="top")
    ax_r.text(0.62, ymax * 1.26,
              "line = the rule\npoints = exact 365-day solves",
              fontsize=9.5, color="#2A6099", va="top")

    fig.suptitle("Vendors sell kWh. kWh is the wrong number to buy on.",
                 fontsize=15.5, y=0.975)
    fig.tight_layout(rect=(0, 0.205, 1, 0.945))

    fig.text(
        0.5, 0.108,
        "saving = min(capacity_kWh, rate_kW × peak_hours) × price_spread",
        ha="center", va="center", fontsize=13, color=INK, family="monospace",
        bbox=dict(boxstyle="round,pad=0.55", facecolor="#EEF2F8",
                  edgecolor="#C6D3E4"),
    )
    fig.text(
        0.5, 0.082,
        f"The binding term is the smaller of the two, and on most installed systems "
        f"it is the inverter. A {FIXED_CAPACITY:g} kWh pack behind a {FIXED_RATE:g} kW "
        f"inverter on a {PEAK_HOURS}-hour peak is a {knee_capacity:g} kWh pack as far "
        f"as the bill is concerned.\nBelow the bind both panels are linear at the same "
        f"${constant:.4f}/yr per kWh/day, which is just the year's price spreads "
        f"summed. Read your own peak-window length off your bill and multiply by your "
        f"inverter rating.",
        ha="center", va="center", fontsize=10, color="0.3",
    )
    fig.text(0.5, 0.022,
             "Golden CO, Xcel RE-TOU, lossless. Verified against the exact DP at 56 "
             "swept points with no mismatches; at a 0.90 round trip the multiplier "
             "scales but the knee does not move.",
             ha="center", fontsize=10, color="0.35")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  capacity sweep at {FIXED_RATE:g} kW: "
          + ", ".join(f"{c:g}kWh=${s:.2f}" for c, s in zip(CAPACITIES, by_capacity)))
    print(f"  rate sweep at {FIXED_CAPACITY:g} kWh: "
          + ", ".join(f"{r:g}kW=${s:.2f}" for r, s in zip(RATES, by_rate)))
    print(f"  knee {knee_capacity:g} kWh / {knee_rate:g} kW; "
          f"constant ${constant:.4f}/yr per kWh/day; plateaus "
          f"${by_capacity.max():.2f} and ${by_rate.max():.2f}/yr")
    print("  every committed annual anchor reproduced, in both regimes")


if __name__ == "__main__":
    main()
