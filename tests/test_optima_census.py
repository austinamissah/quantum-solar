"""``optima_census`` against exhaustive enumeration on tiny instances.

The census mirrors ``dp_solve``'s recurrence forward *and* backward, which is
exactly the kind of hand-rolled index arithmetic that can be subtly wrong while
still producing plausible numbers. So it is checked the way the rest of this
repo checks a fast path: against a slow one that is obviously correct.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from quantum_solar import synthetic_instance
from quantum_solar.dynamic_programming import dp_solve, optima_census
from quantum_solar.problem import BatteryProblem


def enumerate_schedules(problem):
    """Every feasible action sequence, as (cost, actions, per-slot action names)."""
    t = problem.num_slots
    e = problem.charge_energy
    k0 = int(round(problem.initial_soc / e))
    n_max = int(round(problem.capacity / e))
    out = []
    for seq in itertools.product((0, 1, 2), repeat=t):
        k, ok = k0, True
        for a in seq:
            k += (1 if a == 1 else -1 if a == 2 else 0)
            if not 0 <= k <= n_max:
                ok = False
                break
        if not ok or k != k0:
            continue
        cost = sum(problem.price[j] * e * (1 if a == 1 else -1 if a == 2 else 0)
                   for j, a in enumerate(seq))
        out.append((cost, sum(a != 0 for a in seq), seq))
    return out


def reference_census(problem, atol=1e-9):
    rows = enumerate_schedules(problem)
    best = min(r[0] for r in rows)
    optimal = [r for r in rows if abs(r[0] - best) <= atol]
    fewest = min(r[1] for r in optimal)
    minimal = [r for r in optimal if r[1] == fewest]
    names = ("idle", "charge", "discharge")
    slots = tuple(
        tuple(n for a, n in enumerate(names) if any(r[2][j] == a for r in minimal))
        for j in range(problem.num_slots)
    )
    return len(optimal), len(minimal), fewest, slots


@pytest.mark.parametrize("t,seed", [(3, 0), (4, 1), (5, 2), (5, 7)])
def test_census_matches_enumeration(t, seed):
    problem = synthetic_instance(t, seed=seed, capacity=4.0, charge_energy=1.0,
                                 discharge_energy=1.0, initial_soc=2.0)
    got = optima_census(problem)
    n_opt, n_min, acts, slots = reference_census(problem)
    assert got.n_optima == n_opt
    assert got.n_minimal == n_min
    assert got.min_actions == acts
    assert got.slot_actions == slots


def _problem(price, capacity=4.0, initial_soc=2.0):
    t = len(price)
    return BatteryProblem(
        load=np.ones(t), generation=np.zeros(t), price=np.asarray(price, dtype=float),
        capacity=capacity, charge_energy=1.0, discharge_energy=1.0,
        initial_soc=initial_soc,
    )


def test_flat_price_day_has_exactly_one_minimal_optimum():
    """No price spread means no arbitrage: the only minimal plan is to do nothing.

    ``n_optima`` meanwhile counts every feasible schedule, because in a lossless
    model each charge is cancelled by its discharge. That gap is the reason
    ``n_minimal`` exists.
    """
    census = optima_census(_problem([0.14] * 8))
    assert census.n_minimal == 1
    assert census.min_actions == 0
    assert census.n_optima > 1
    assert all(a == ("idle",) for a in census.slot_actions)


def test_peak_discharge_is_forced_and_cheap_hours_are_free():
    """One expensive hour: discharging into it is forced, the refill hour is not."""
    census = optima_census(_problem([0.1, 0.1, 0.9, 0.1, 0.1]))
    assert census.slot_actions[2] == ("discharge",)
    assert census.forced()[2] == "discharge"
    # The cheap hours can each either idle or charge, so none of them is forced.
    for j in (0, 1, 3, 4):
        assert set(census.slot_actions[j]) == {"idle", "charge"}


def test_census_optimum_agrees_with_dp_solve():
    """The census's minimal action count must match the schedule dp_solve returns."""
    problem = synthetic_instance(6, seed=3, capacity=4.0, charge_energy=1.0,
                                 discharge_energy=1.0, initial_soc=2.0)
    solution = dp_solve(problem)
    charge, discharge = problem.decode(solution.x)
    census = optima_census(problem)
    assert census.min_actions <= int(charge.sum() + discharge.sum())
