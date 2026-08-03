"""What does halving the qubit count cost per year, in dollars?

The encoding study reports regret as a percentage of one synthetic day's battery
value. That is the right unit for comparing encodings but the wrong one for a
deployment question, and it is not safely convertible: the real tariff and the
seasonal generation profile weight errors differently than a single synthetic day
does.

**A prediction that turned out wrong, recorded because the reasoning was wrong
too.** The RE-TOU weekend schedule is flat off-peak, so all 104 weekend days earn
exactly $0 of battery arbitrage, and we expected those days to *dilute* annual
regret below the per-day figure. They cannot: a $0 day contributes nothing to the
lost-dollars numerator and nothing to the battery-value denominator, so it drops
out of the ratio entirely rather than pulling it toward zero.

The measurement went the other way — ``cp3`` loses 75% annually against 32.5% on
the synthetic day. The real mechanism is **concentration**: the tariff pushes the
battery's whole value into a minority of high-spread days, and capturing a large
spread needs a deep charge/discharge cycle held across many slots. That is
precisely the schedule shape checkpointing forbids, so the encoding's error is
largest exactly where the money is. Averaging a synthetic day's regret would have
understated the annual cost by more than 2x.

So this prices each encoding properly: run its schedule through the exact same
365-day loop the headline annual number uses (``annual_from_inputs`` with a
``solver`` hook, so the three-way attribution stays computed in one place), and
difference the resulting annual bill against the exact DP optimum.

Everything is read from the committed snapshot — no network, no API key.

Run::

    python scripts/annual_encoding_cost.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from quantum_solar import (  # noqa: E402
    Encoding,
    default_weights,
    max_sound_spacing,
    num_vars,
)
from quantum_solar.annual import annual_from_inputs  # noqa: E402
from quantum_solar.data import load_profile  # noqa: E402
from quantum_solar.data.nrel import price_to_slots, to_slots  # noqa: E402
from quantum_solar.qubo_search import qubo_min_exact  # noqa: E402

SNAPSHOT = ROOT / "docs" / "figures" / "annual_golden_co.json"

# Checkpoint spacings are PINNED, not derived. The real instance (capacity 10.0,
# charge_energy 2.0 -> n_max=5, k_0=2) has a sound ceiling of 5, looser than the
# synthetic Q=3 family's 3; both are reported so the rigidity/cost trade is visible.
SPACINGS = (3, 5)


def main() -> None:
    snap = json.loads(SNAPSHOT.read_text())
    generation = np.asarray(snap["generation"], dtype=float)
    weekday = [np.asarray(p, dtype=float) for p in snap["price_weekday"]]
    weekend = [np.asarray(p, dtype=float) for p in snap["price_weekend"]]
    capacity = float(snap["capacity"])
    charge_energy = float(snap["charge_energy"])

    def price_for(month, is_weekend):
        return price_to_slots(weekend[month] if is_weekend else weekday[month], 24)

    def load_for(month, dtype):
        return load_profile(month, dtype)  # load_profile months are 0-based

    kwargs = dict(capacity=capacity, charge_energy=charge_energy)
    exact_year = annual_from_inputs(generation, price_for, load_for, **kwargs)
    battery_value = exact_year.battery_savings

    probe = None  # one representative day, to report qubit counts and the ceiling

    def make_solver(encoding):
        def solve(problem):
            nonlocal probe
            probe = problem
            return qubo_min_exact(problem, default_weights(problem), encoding)
        return solve

    encodings = [("exact", Encoding.EXACT)]
    for k in SPACINGS:
        encodings.append((f"cp{k}", Encoding.checkpoint(k)))
        encodings.append((f"cp{k}band", Encoding.checkpoint(k, banded=True)))
    encodings += [("wd4", Encoding.window_drift(4)), ("center", Encoding.center_anchor()),
                  ("none", Encoding.NONE)]

    print(f"Golden CO, {snap['rate_label']} — battery value (exact DP) "
          f"= ${battery_value:,.2f}/yr")
    print(f"capacity={capacity} kWh  charge_energy={charge_energy} kWh  "
          f"solar {snap['system_kw']} kW\n")

    rows = []
    for name, encoding in encodings:
        year = annual_from_inputs(generation, price_for, load_for,
                                  solver=make_solver(encoding), **kwargs)
        infeasible = sum(1 for d in year.days if not d.feasible)
        captured = year.battery_savings
        rows.append((name, encoding, captured, battery_value - captured, infeasible))

    ceiling = max_sound_spacing(probe)
    weekend_days = sum(1 for d in exact_year.days if d.day_type == "weekend")
    zero_days = sum(1 for d in exact_year.days if abs(d.battery_savings) < 1e-9)
    print(f"sound checkpoint ceiling on this instance: k <= {ceiling}   "
          f"weekend days: {weekend_days}   days earning $0: {zero_days}\n")

    header = (f"{'encoding':<10} {'qubits':>7} {'captured $/yr':>14} {'lost $/yr':>10} "
              f"{'lost %':>7} {'infeasible days':>16}")
    print(header)
    print("-" * len(header))
    for name, encoding, captured, lost, infeasible in rows:
        flag = f"{infeasible}" if infeasible == 0 else f"{infeasible}  (bill invalid)"
        print(f"{name:<10} {num_vars(probe, encoding):>7} {captured:>14,.2f} "
              f"{lost:>10,.2f} {100 * lost / battery_value:>7.2f} {flag:>16}")


if __name__ == "__main__":
    main()
