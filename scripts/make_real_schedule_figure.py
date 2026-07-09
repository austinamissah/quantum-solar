"""Regenerate the web real-day schedule figure (docs/figures/web/schedule_real_day.png).

Reads the committed real-instance snapshot (docs/figures/web/schedule_real_day.json)
and re-renders the Golden, CO summer-weekday schedule with non-technical framing
and blog-readable fonts, reusing quantum_solar.plotting.plot_schedule. Everything
is derived from committed data (the snapshot's PVWatts generation, URDB price, and
ResStock load); the optimal schedule is recomputed with the exact DP solver. No
network, no experiments re-run.

Like the mass-ratio web figure, this writes to docs/figures/web/ (curated),
separate from the experiment/demo outputs.

    python scripts/make_real_schedule_figure.py

Caption suggestion (for the blog post):
  One real summer weekday for a Colorado home in Golden, CO. Top: the time-of-use
  electricity price (red), the household's electricity use (blue), and its rooftop
  solar output (orange). Bottom: the cost-optimal battery plan our solver found,
  charging (green) when power is cheap or solar is plentiful and discharging (red)
  into the shaded 5-9pm peak-price window, with the resulting battery level
  overlaid. Every input is real: NREL PVWatts solar, Xcel Energy's Colorado
  time-of-use tariff (via URDB), and an NREL ResStock household load profile.

  About the lone green bar just after the peak: the plan deliberately drains the
  battery during the 5-9pm peak, selling at $0.381/kWh what it can replace at
  $0.139/kWh. Because the model requires the battery to end the day at its
  starting level, it must buy those kWh back at the first cheap hour after the
  peak. The post-peak cheap hours are all equally priced, so the solver picked one
  of several tied-optimal placements for that refill: its exact hour is arbitrary,
  its existence is forced by the end-of-day constraint.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import json  # noqa: E402

import numpy as np  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantum_solar import BatteryProblem, dp_solve  # noqa: E402
from quantum_solar.plotting import plot_schedule  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "docs" / "figures" / "web" / "schedule_real_day.json"
OUT = Path(__file__).resolve().parent.parent / "docs" / "figures" / "web" / "schedule_real_day.png"

PEAK_START, PEAK_END = 17, 21  # 5-9pm on-peak window


def main():
    d = json.loads(DATA.read_text())
    problem = BatteryProblem(
        generation=np.array(d["generation"]), load=np.array(d["load"]),
        price=np.array(d["price"]), capacity=d["capacity"],
        charge_energy=d["charge_energy"], discharge_energy=d["discharge_energy"],
        initial_soc=d["initial_soc"],
    )
    solution = dp_solve(problem)
    charge, _ = problem.decode(solution.x)
    e = problem.charge_energy

    fig = plot_schedule(problem, solution)  # reuse the plotting module
    ax_top, ax_bot, ax_energy, ax_soc = fig.axes[0], fig.axes[1], fig.axes[2], fig.axes[3]

    # Plain-language titles and labels (no em-dashes).
    ax_top.set_title("A summer weekday for a Colorado home (Golden, CO)", fontsize=16, pad=10)
    ax_bot.set_title(
        f"The cost-optimal battery plan (net bill ${solution.true_energy:.2f} for the day)",
        fontsize=15, pad=10)
    ax_top.set_ylabel("electricity price ($/kWh)", fontsize=12, color="C3")
    ax_energy.set_ylabel("energy (kWh)", fontsize=12)
    ax_bot.set_ylabel("battery action (kWh)", fontsize=12)
    ax_soc.set_ylabel("battery level (kWh)", fontsize=12)
    ax_bot.set_xlabel("hour of day", fontsize=12)

    # Mark the 5-9pm peak-price window on both panels.
    for ax in (ax_top, ax_bot):
        ax.axvspan(PEAK_START, PEAK_END, color="0.6", alpha=0.15, zorder=0)
    y0, y1 = ax_top.get_ylim()
    ax_top.text((PEAK_START + PEAK_END) / 2, y0 + 0.28 * (y1 - y0), "5-9pm peak price",
                ha="center", va="center", fontsize=10, color="0.2",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="0.6", alpha=0.9))

    # Convey charge/discharge meaning through a legend on the bottom panel.
    ax_bot.legend(
        handles=[Patch(fc="C2", label="charge (buy)"),
                 Patch(fc="C3", label="discharge (use/sell)")],
        loc="lower left", fontsize=9.5, framealpha=0.9)

    # Give the battery-level (SoC) line the lower ~60% of the panel so the top is
    # clear for the refill annotation (presentation only; the data is unchanged).
    ax_soc.set_ylim(-0.5, 1.7 * problem.capacity)
    ax_bot.set_ylim(-1.3 * e, 1.55 * e)

    # Annotate the post-peak refill bar, in the now-clear top area directly above it.
    refill = next((i for i in range(len(charge)) if charge[i] and i >= PEAK_END), None)
    if refill is not None:
        bar_x = refill + 0.5
        ax_bot.annotate(
            "refill for tomorrow\n(day must end where it started)",
            xy=(bar_x, 1.02 * e), xytext=(bar_x, 1.32 * e),
            ha="right", va="center", fontsize=9.5, color="0.15",
            arrowprops=dict(arrowstyle="->", color="0.3", lw=1.3),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="0.6", alpha=0.95))

    for ax in (ax_top, ax_bot, ax_energy, ax_soc):
        ax.tick_params(labelsize=10)
    legend = ax_energy.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontsize(10)

    # Explicit margins so nothing clips at the committed pixel size (no bbox_inches).
    fig.set_size_inches(9.6, 6.4)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.92, bottom=0.09, hspace=0.34)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=119)  # 9.6 * 119 = 1142 px wide
    print(f"wrote {OUT} (net bill ${solution.true_energy:.2f}, feasible={solution.feasible})")


if __name__ == "__main__":
    main()
