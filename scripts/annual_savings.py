"""Annualized battery-savings headline + per-month savings figure.

Reads the committed annual snapshot (docs/figures/annual_golden_co.json: one
year of PVWatts generation and the Xcel RE-TOU weekday/weekend price schedules
for Golden, CO) and the committed ResStock load profiles, runs the exact 365-day
DP via quantum_solar.annual.annual_from_inputs, prints the three-way counterfactual
headline (no system / solar only / solar + optimal battery), and renders the
per-month battery-savings curve. Everything is derived from committed data — no
network, no API key, nothing re-fetched.

    python scripts/annual_savings.py

The plotted quantity is mean battery savings per WEEKDAY per month. Battery
arbitrage depends only on the on/off-peak price spread (and holds solar fixed),
and every weekday in a season shares one price schedule, so this curve is a dead-
flat winter level and a raised summer plateau (Jun-Sep, the tariff's summer
season), stepping exactly on the season boundary. (Weekdays, not all days, are
plotted on purpose: a per-all-days mean would wobble with each month's weekend
count — a real calendar effect, not a mapping error — masking the diagnostic.
Weekends earn $0: the RE-TOU weekend schedule is flat off-peak.) A kink or jump
anywhere but the season boundary means the month->season map or weekday
classification is off — a correctness signal, not decoration.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import json  # noqa: E402

import numpy as np  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from quantum_solar.annual import annual_from_inputs  # noqa: E402
from quantum_solar.data import load_profile  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "docs" / "figures" / "annual_golden_co.json"
OUT = ROOT / "docs" / "figures" / "annual_savings_by_month.png"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SUMMER_MONTHS0 = {5, 6, 7, 8}  # Jun-Sep, the RE-TOU summer season


def compute(snapshot):
    gen = np.array(snapshot["generation"], dtype=float)
    price_weekday = np.array(snapshot["price_weekday"], dtype=float)
    price_weekend = np.array(snapshot["price_weekend"], dtype=float)

    def price_for(month, weekend):
        return price_weekend[month] if weekend else price_weekday[month]

    return annual_from_inputs(
        gen, price_for, load_profile,
        capacity=snapshot["capacity"],
        charge_energy=snapshot["charge_energy"],
        discharge_energy=snapshot["discharge_energy"],
    )


def per_month_weekday_mean(result):
    """Mean battery savings ($) over the WEEKDAYS of each 0-based month.

    Weekday-only so the curve isolates the price-spread (season) signal: every
    weekday in a season shares one schedule, so a correct mapping yields a flat
    plateau. Including weekends would fold in each month's weekend count (a real
    calendar effect) and blur that diagnostic. Weekends are $0 (flat off-peak).
    """
    total = np.zeros(12)
    ndays = np.zeros(12)
    for r in result.days:
        if r.day_type == "weekday":
            total[r.month] += r.battery_savings
            ndays[r.month] += 1
    return total / ndays


def main():
    snapshot = json.loads(SNAP.read_text())
    result = compute(snapshot)

    print(f"Annualized savings — {snapshot['location']} "
          f"({snapshot['system_kw']} kW PV, {snapshot['capacity']} kWh battery)")
    print(f"  tariff: Xcel RE-TOU (URDB {snapshot['rate_label']}), snapshot {snapshot['snapshot_date']}")
    print(f"  no system (price x load):    ${result.no_system_cost:8.2f}")
    print(f"  solar only (battery idle):   ${result.solar_only_cost:8.2f}")
    print(f"  solar + optimal battery:     ${result.optimized_cost:8.2f}")
    print(f"  --> solar savings:           ${result.solar_savings:8.2f}/yr")
    print(f"  --> battery savings (alone): ${result.battery_savings:8.2f}/yr")

    weekday_mean = per_month_weekday_mean(result)

    # Sanity check: because every weekday in a season shares one price schedule,
    # each season's weekday mean must be a FLAT plateau, stepping only at the
    # summer boundary. Any nonzero within-plateau spread => a month is mapped to
    # the wrong season or a day is misclassified.
    summer = np.array([m in SUMMER_MONTHS0 for m in range(12)])
    summer_vals, winter_vals = weekday_mean[summer], weekday_mean[~summer]
    span = weekday_mean.max() - weekday_mean.min()
    print("\nper-month mean battery savings per weekday ($/weekday):")
    for m in range(12):
        tag = "summer" if summer[m] else "winter"
        print(f"  {MONTHS[m]} ({tag}): {weekday_mean[m]:.4f}")
    print(f"summer plateau spread: {np.ptp(summer_vals):.4f}   "
          f"winter plateau spread: {np.ptp(winter_vals):.4f}   "
          f"summer-vs-winter step: {summer_vals.mean() - winter_vals.mean():.4f}")
    # Plateaus must be flat to floating-point noise and must not overlap.
    if summer_vals.min() <= winter_vals.max():
        print("WARNING: summer and winter plateaus overlap — check month->season mapping!")
    if max(np.ptp(summer_vals), np.ptp(winter_vals)) > 1e-6 * max(1.0, span):
        print("WARNING: a plateau is not flat — month-boundary discontinuity (mapping/weekday bug)!")
    else:
        print("OK: both plateaus flat; single step at the Jun/Oct season boundary.")

    _render(weekday_mean, summer, result, snapshot)


def _render(weekday_mean, summer, result, snapshot):
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(9.0, 4.8))
    x = np.arange(12)

    # Shade the summer season band.
    lo = min(s for s, m in zip(range(12), summer) if m)
    hi = max(s for s, m in zip(range(12), summer) if m)
    ax.axvspan(lo - 0.5, hi + 0.5, color="#f4a300", alpha=0.12, zorder=0)
    ax.text((lo + hi) / 2, weekday_mean.max() * 1.045, "summer TOU season (Jun-Sep)",
            ha="center", va="bottom", fontsize=9.5, color="#8a5a00")

    ax.plot(x, weekday_mean, "-o", color="#1f77b4", lw=2.0, ms=6, zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(MONTHS)
    ax.set_ylabel("battery savings per weekday ($/day)", fontsize=11, parse_math=False)
    ax.set_ylim(0, weekday_mean.max() * 1.18)
    ax.set_title(
        f"Battery arbitrage savings by month - {snapshot['location']} "
        f"({snapshot['system_kw']} kW PV, {snapshot['capacity']} kWh battery)\n"
        f"${result.battery_savings:.0f}/yr from the battery alone "
        f"(solar held fixed); weekends flat off-peak -> $0",
        fontsize=11.5, pad=12, parse_math=False)
    ax.grid(True, axis="y", alpha=0.3)
    ax.margins(x=0.02)

    fig.subplots_adjust(left=0.09, right=0.97, top=0.84, bottom=0.10)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=120)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
