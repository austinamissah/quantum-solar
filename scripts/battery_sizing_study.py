"""Does the sizing rule generalize across tariffs, and does a battery pay for itself?

Two questions that close out the sizing story, both written to
``docs/results/capacity_rate_sensitivity.json`` and reported in
``docs/results/capacity-rate-sensitivity.md``:

1. **Peak-window sweep.** ``saving = min(capacity, rate x peak_hours) x spread``
   was measured only against Colorado's 4-hour block, and the whole rule turns on
   ``peak_hours``. This re-runs it on synthetic tariffs at 3, 4, 5 and 6 peak
   hours with the spread held fixed, so a reader can take the window length off
   their own bill and get their own saturation point.

2. **Payback.** The number a buyer actually needs, and the one the project has
   never stated. Annual battery savings come from the committed snapshot via the
   same 365-day DP the README quotes; installed cost is swept across a plausible
   range rather than pinned to one vendor.

Synthetic prices, committed snapshot, exact DP. No network.

    python scripts/battery_sizing_study.py
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from quantum_solar import dp_solve  # noqa: E402
from quantum_solar.annual import annual_from_inputs  # noqa: E402
from quantum_solar.data import load_profile  # noqa: E402
from quantum_solar.problem import BatteryProblem  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SNAP = ROOT / "docs" / "figures" / "annual_golden_co.json"
OUT = ROOT / "docs" / "results" / "capacity_rate_sensitivity.json"

# Xcel RE-TOU summer weekday, the anchor instance: off-peak level and on/off spread.
OFF_PEAK, SPREAD = 0.13926, 0.24183
PEAK_END = 20            # peak ends at hour 20 and grows backward as it lengthens
PEAK_HOURS = (3, 4, 5, 6)
CAPACITIES = (2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 20.0)   # kWh, at RATE
RATES = (0.5, 1.0, 2.0, 2.5, 5.0)                                 # kW, at CAPACITY
RATE, CAPACITY = 2.0, 10.0

# Installed cost of a ~10 kWh residential system, swept rather than pinned to one
# vendor. Warranties in this class are typically 10 years, which is the number the
# payback has to beat.
INSTALLED_COSTS = (5000, 7000, 9000, 11500, 14000)
WARRANTY_YEARS = 10


def synthetic_day(peak_hours: int) -> np.ndarray:
    """A 24-hour two-tier tariff with ``peak_hours`` on-peak, spread held fixed.

    The window **ends** at ``PEAK_END`` and grows backward into the afternoon,
    which is how utilities actually widen an evening peak and — the reason it
    matters here — keeps the post-peak refill window fixed at 3 hours. Growing it
    forward instead would shrink the hours available to return the battery to its
    starting level, and that constraint, not the rule under test, would bind.
    """
    price = np.full(24, OFF_PEAK)
    price[PEAK_END - peak_hours + 1:PEAK_END + 1] = OFF_PEAK + SPREAD
    return price


def saving(price: np.ndarray, capacity: float, rate: float) -> float:
    """Exact daily saving of the battery against idling it, on a unit load."""
    problem = BatteryProblem(
        load=np.ones(24), generation=np.zeros(24), price=price,
        capacity=capacity, charge_energy=rate, discharge_energy=rate,
        # Half full, snapped to the rate grid: clear of both extremes, where the
        # charge headroom (starting full) or the refill window would bind instead.
        initial_soc=round((capacity / 2) / rate) * rate,
    )
    idle = float(problem.energy(np.zeros(2 * problem.num_slots, dtype=np.int8)))
    return idle - float(dp_solve(problem).true_energy)


def sweep(peak_hours: int) -> dict:
    """Capacity and rate sweeps at one window length, each point checked against the rule."""
    price = synthetic_day(peak_hours)

    def point(capacity, rate):
        got = saving(price, capacity, rate)
        predicted = min(capacity, rate * peak_hours) * SPREAD
        return {"capacity": capacity, "rate": rate, "saving": round(got, 4),
                "predicted": round(predicted, 4),
                "matches_rule": bool(abs(got - predicted) < 5e-4)}

    by_capacity = [point(c, RATE) for c in CAPACITIES]
    ceiling = max(p["saving"] for p in by_capacity)
    knee = min(p["capacity"] for p in by_capacity if abs(p["saving"] - ceiling) < 5e-4)
    return {
        "peak_hours": peak_hours,
        "peak_window": [PEAK_END - peak_hours + 1, PEAK_END],
        "useful_capacity_kwh": round(RATE * peak_hours, 4),
        "saturation_capacity_kwh": knee,
        "daily_ceiling": round(ceiling, 4),
        "by_capacity": by_capacity,
        "by_rate": [point(CAPACITY, r) for r in RATES],
    }


def annual_savings_for(snapshot, capacity: float, rate: float) -> float:
    """Battery-alone savings over the full year, the same call the README quotes."""
    generation = np.array(snapshot["generation"], dtype=float)
    weekday = np.array(snapshot["price_weekday"], dtype=float)
    weekend = np.array(snapshot["price_weekend"], dtype=float)
    result = annual_from_inputs(
        generation, lambda m, w: weekend[m] if w else weekday[m], load_profile,
        capacity=capacity, charge_energy=rate, discharge_energy=rate,
    )
    return float(result.battery_savings)


def main() -> None:
    snapshot = json.loads(SNAP.read_text())
    windows = [sweep(h) for h in PEAK_HOURS]

    baseline = annual_savings_for(snapshot, CAPACITY, RATE)
    upgraded = annual_savings_for(snapshot, CAPACITY, 2.5)
    payback = [
        {"installed_cost": c,
         "years_at_2kw": round(c / baseline, 1),
         "years_at_2p5kw": round(c / upgraded, 1),
         "within_warranty": bool(c / baseline <= WARRANTY_YEARS)}
        for c in INSTALLED_COSTS
    ]

    record = {
        "_source": "Generated by scripts/battery_sizing_study.py. Peak-window sweeps "
                   "use synthetic two-tier tariffs at a fixed spread; annual savings "
                   "and payback use the committed snapshot "
                   "docs/figures/annual_golden_co.json via the same 365-day DP the "
                   "README quotes. Exact DP throughout, no network.",
        "_upper_bounds": "Every saving here is an UPPER BOUND, so every payback is a "
                         "LOWER bound. v1 is lossless and assumes buy == sell: "
                         "round-trip losses would cut both the delivered energy and "
                         "the effective spread, and an export price below the import "
                         "price would lower the ceiling. Real payback is longer than "
                         "the table says.",
        "price_spread": SPREAD,
        "off_peak_price": OFF_PEAK,
        "rule": "saving = min(capacity_kWh, rate_kW * peak_hours) * price_spread",
        "swept_at_rate_kw": RATE,
        "swept_at_capacity_kwh": CAPACITY,
        "windows": windows,
        "annual": {
            "battery_savings_2kw": round(baseline, 2),
            "battery_savings_2p5kw": round(upgraded, 2),
            "rate_upgrade_gain": round(upgraded - baseline, 2),
            "capacity_upgrade_gain": round(
                annual_savings_for(snapshot, 20.0, RATE) - baseline, 2),
            "warranty_years": WARRANTY_YEARS,
            "payback": payback,
        },
    }
    OUT.write_text(json.dumps(record, indent=1) + "\n")

    mismatches = sum(1 for w in windows for k in ("by_capacity", "by_rate")
                     for p in w[k] if not p["matches_rule"])
    print(f"peak-window sweep ({len(PEAK_HOURS)} windows, spread ${SPREAD})")
    print(f"  {'peak hrs':>9} {'window':>9} {'rule kWh':>9} {'knee kWh':>9} {'ceiling':>9}")
    for w in windows:
        lo, hi = w["peak_window"]
        print(f"  {w['peak_hours']:>9} {f'{lo}-{hi}':>9} {w['useful_capacity_kwh']:>9} "
              f"{w['saturation_capacity_kwh']:>9} ${w['daily_ceiling']:>8.4f}")
    print(f"  rule mismatches: {mismatches}")
    print()
    print(f"annual battery savings: ${baseline:.2f}/yr at {RATE} kW, "
          f"${upgraded:.2f}/yr at 2.5 kW (+${upgraded - baseline:.2f})")
    print(f"  {'installed':>10} {'yrs @2kW':>9} {'yrs @2.5kW':>11} {'<= warranty':>12}")
    for row in payback:
        print(f"  ${row['installed_cost']:>9,} {row['years_at_2kw']:>9} "
              f"{row['years_at_2p5kw']:>11} {str(row['within_warranty']):>12}")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
