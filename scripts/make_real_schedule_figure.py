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
  charging (green, up) when power is cheap or solar is plentiful and discharging
  (red, down) into the shaded 5-9pm peak-price window, with the resulting battery
  level overlaid. Every input is real: NREL PVWatts solar, Xcel Energy's Colorado
  time-of-use tariff (via URDB), and an NREL ResStock household load profile.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import json  # noqa: E402

import numpy as np  # noqa: E402

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

    fig = plot_schedule(problem, solution)  # reuse the plotting module
    ax_top, ax_bot, ax_energy, ax_soc = fig.axes[0], fig.axes[1], fig.axes[2], fig.axes[3]

    # Plain-language titles and labels (no em-dashes).
    ax_top.set_title("A summer weekday for a Colorado home (Golden, CO)", fontsize=16, pad=10)
    ax_bot.set_title(
        f"The cost-optimal battery plan (net bill ${solution.true_energy:.2f} for the day)",
        fontsize=15, pad=10)
    ax_top.set_ylabel("electricity price ($/kWh)", fontsize=12, color="C3")
    ax_energy.set_ylabel("energy (kWh)", fontsize=12)
    ax_bot.set_ylabel("battery: charging up / discharging down (kWh)", fontsize=12)
    ax_soc.set_ylabel("battery level (kWh)", fontsize=12)
    ax_bot.set_xlabel("hour of day", fontsize=12)

    # Mark the 5-9pm peak-price window on both panels.
    for ax in (ax_top, ax_bot):
        ax.axvspan(PEAK_START, PEAK_END, color="0.6", alpha=0.15, zorder=0)
    ax_top.text((PEAK_START + PEAK_END) / 2, ax_top.get_ylim()[1], " 5-9pm peak price ",
                ha="center", va="top", fontsize=10, color="0.3")

    # Readable ticks and legend at blog-embed width.
    for ax in (ax_top, ax_bot, ax_energy, ax_soc):
        ax.tick_params(labelsize=10)
    legend = ax_energy.get_legend()
    if legend is not None:
        for text in legend.get_texts():
            text.set_fontsize(10)

    fig.set_size_inches(9.2, 6.2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=126, bbox_inches="tight")  # ~1140px wide
    print(f"wrote {OUT} (net bill ${solution.true_energy:.2f})")


if __name__ == "__main__":
    main()
