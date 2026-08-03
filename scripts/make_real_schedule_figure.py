"""Regenerate the web real-day schedule figures (docs/figures/web/schedule_real_day*).

Renders one Golden, CO day per **seasonal bucket** -- summer/winter x
weekday/weekend -- with non-technical framing and blog-readable fonts, reusing
quantum_solar.plotting.plot_schedule.

Inputs are assembled the same way ``annual.annual_from_inputs`` assembles them,
so the three of them cannot disagree on season or day type: the day index picks
the PVWatts generation day, and ``data.calendar`` derives the price month, the
weekday/weekend URDB schedule, and the load bucket from that *same* index. (The
previous hand-written snapshot predated that fix and labelled a June solar day
with a July price.) Everything is read from the committed annual snapshot and the
committed ResStock profiles; the optimal schedule is recomputed with the exact DP
solver. No network, no experiments re-run.

``schedule_real_day.json`` is now an *output*: it records exactly the four
instances that were plotted, so the figures are reproducible from it.

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
from quantum_solar import dp_solve  # noqa: E402
from quantum_solar.data import load_profile  # noqa: E402
from quantum_solar.data.calendar import day_to_month, day_type, is_weekend  # noqa: E402
from quantum_solar.data.nrel import build_instance, price_to_slots, to_slots  # noqa: E402
from quantum_solar.plotting import plot_schedule  # noqa: E402

WEB = Path(__file__).resolve().parent.parent / "docs" / "figures" / "web"
SNAPSHOT = Path(__file__).resolve().parent.parent / "docs" / "figures" / "annual_golden_co.json"
DATA = WEB / "schedule_real_day.json"

PEAK_START, PEAK_END = 17, 21  # 5-9pm on-peak window

# One representative day per seasonal bucket. Summer is Jun-Sep (the RE-TOU
# tariff season); the month is a target and the day is the first one in it whose
# weekday/weekend type matches, so every bucket is a real AMY-2018 calendar day.
BUCKETS = (
    ("summer_weekday", 6, "weekday", "A summer weekday"),
    ("summer_weekend", 6, "weekend", "A summer weekend day"),
    ("winter_weekday", 0, "weekday", "A winter weekday"),
    ("winter_weekend", 0, "weekend", "A winter weekend day"),
)


def pick_day(month: int, wanted: str) -> int:
    """First AMY-2018 day in ``month`` of the requested weekday/weekend type."""
    for day in range(365):
        if day_to_month(day) == month and day_type(day) == wanted:
            return day
    raise ValueError(f"no {wanted} in month {month}")


def build_bucket(snap, day: int):
    """Assemble one day exactly as the annual loop does (season-coherent by construction)."""
    month, weekend = day_to_month(day), is_weekend(day)
    generation = to_slots(np.asarray(snap["generation"], dtype=float), day, 24)
    prices = snap["price_weekend"] if weekend else snap["price_weekday"]
    price = price_to_slots(np.asarray(prices[month], dtype=float), 24)
    load = to_slots(load_profile(month, day_type(day)), day=0, num_slots=24)
    return build_instance(generation, load, price,
                          capacity=float(snap["capacity"]),
                          charge_energy=float(snap["charge_energy"]))


def render(problem, solution, headline, out_path):
    charge, _ = problem.decode(solution.x)
    e = problem.charge_energy
    has_peak = float(problem.price.max() - problem.price.min()) > 1e-9

    fig = plot_schedule(problem, solution)  # reuse the plotting module
    ax_top, ax_bot, ax_energy, ax_soc = fig.axes[0], fig.axes[1], fig.axes[2], fig.axes[3]

    # Plain-language titles and labels (no em-dashes).
    ax_top.set_title(f"{headline} for a Colorado home (Golden, CO)", fontsize=16, pad=10)
    ax_bot.set_title(
        f"The cost-optimal battery plan (net bill ${solution.true_energy:.2f} for the day)",
        fontsize=15, pad=10)
    ax_top.set_ylabel("electricity price ($/kWh)", fontsize=12, color="C3")
    ax_energy.set_ylabel("energy (kWh)", fontsize=12)
    ax_bot.set_ylabel("battery action (kWh)", fontsize=12)
    ax_soc.set_ylabel("battery level (kWh)", fontsize=12)
    ax_bot.set_xlabel("hour of day", fontsize=12)

    # A flat tariff would otherwise be auto-scaled to a ~$0.01 window, making a
    # constant price read as structure. Pin the axis so flat looks flat.
    if not has_peak:
        ax_top.set_ylim(0.0, float(problem.price.max()) * 1.7)
        ax_bot.text(
            12, 0.55 * e,
            "Flat off-peak price all day: no arbitrage to capture,\nso the battery stays idle",
            ha="center", va="center", fontsize=11, color="0.15",
            bbox=dict(boxstyle="round,pad=0.4", fc="white", ec="0.6", alpha=0.95))

    # Mark the 5-9pm peak-price window on both panels (weekends are flat: no peak).
    if has_peak:
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
    if has_peak and refill is not None:
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
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=119)  # 9.6 * 119 = 1142 px wide


def main():
    snap = json.loads(SNAPSHOT.read_text())
    record = {
        "_source": "Generated by scripts/make_real_schedule_figure.py from "
                   "docs/figures/annual_golden_co.json and the committed ResStock "
                   "profiles. Season, day type, price month, and load bucket all "
                   "derive from the same day index (see data/calendar.py, AMY 2018).",
        "location": snap["location"], "system_kw": snap["system_kw"],
        "capacity": snap["capacity"], "charge_energy": snap["charge_energy"],
        "buckets": {},
    }
    for name, month, wanted, headline in BUCKETS:
        day = pick_day(month, wanted)
        problem = build_bucket(snap, day)
        solution = dp_solve(problem)
        out = WEB / ("schedule_real_day.png" if name == "summer_weekday"
                     else f"schedule_real_day_{name}.png")
        render(problem, solution, headline, out)
        record["buckets"][name] = {
            "day": day, "month": day_to_month(day), "day_type": day_type(day),
            "generation": [round(float(v), 6) for v in problem.generation],
            "load": [round(float(v), 6) for v in problem.load],
            "price": [round(float(v), 6) for v in problem.price],
            "initial_soc": float(problem.initial_soc),
            "net_bill": round(float(solution.true_energy), 4),
            "feasible": bool(solution.feasible),
        }
        print(f"wrote {out.name:<38} day={day:>3} ({day_type(day):>7}) "
              f"net bill ${solution.true_energy:>6.2f}  feasible={solution.feasible}")
    DATA.write_text(json.dumps(record, indent=1) + "\n")
    print(f"wrote {DATA.name} with {len(record['buckets'])} buckets")


if __name__ == "__main__":
    main()
