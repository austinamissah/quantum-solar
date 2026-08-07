"""The DP baseline: exact, matches brute force, and scales in T."""

import time

import numpy as np
import pytest

from quantum_solar import build_qubo, brute_force_solve, dp_solve, synthetic_instance


def test_dp_finds_known_optimum(tiny_problem):
    solution = dp_solve(tiny_problem)
    c, d = tiny_problem.decode(solution.x)

    assert np.array_equal(c, [1, 0])
    assert np.array_equal(d, [0, 1])
    assert solution.feasible
    assert np.isclose(solution.true_energy, -2.0)


def test_dp_matches_brute_force(small_problem, small_weights):
    qubo = build_qubo(small_problem, small_weights)
    brute = brute_force_solve(small_problem, qubo)
    dp = dp_solve(small_problem)

    # Two exact solvers may return different but equally-optimal schedules (e.g.
    # under flat price blocks), so compare optimal cost and feasibility rather
    # than identical decision vectors.
    assert brute.feasible and dp.feasible
    assert np.isclose(dp.true_energy, brute.true_energy)


def test_dp_scales_to_full_day():
    problem = synthetic_instance(num_slots=24, seed=3)
    start = time.perf_counter()
    solution = dp_solve(problem)
    elapsed = time.perf_counter() - start

    assert solution.feasible
    assert elapsed < 1.0  # polynomial: a full day solves near-instantly


def test_dp_rejects_off_grid_initial_soc():
    from quantum_solar import BatteryProblem

    # initial_soc=5 is not a multiple of charge_energy=2: the DP grid would round
    # it and return an infeasible (capacity-exceeding) schedule. Fail loud instead.
    problem = BatteryProblem(
        generation=np.zeros(3), load=np.zeros(3), price=np.array([1.0, 3.0, 1.0]),
        capacity=10.0, charge_energy=2.0, discharge_energy=2.0, initial_soc=5.0,
    )
    with pytest.raises(ValueError, match="initial_soc=5.0 is not a multiple"):
        dp_solve(problem)


def test_dp_rejects_off_grid_capacity():
    """The same failure one axis over, found while sweeping capacity and rate.

    ``n_max = round(capacity / e)`` rounds *up* past a half step, so a 10 kWh
    battery at 6 kWh/slot got a top grid level of 12 kWh: the DP returned a
    schedule reaching 12.0 kWh and reported it optimal and feasible.
    """
    from quantum_solar import BatteryProblem

    problem = BatteryProblem(
        generation=np.zeros(8), load=np.ones(8),
        price=np.array([0.1, 0.1, 0.1, 0.9, 0.9, 0.1, 0.1, 0.1]),
        capacity=10.0, charge_energy=6.0, discharge_energy=6.0, initial_soc=0.0,
    )
    with pytest.raises(ValueError, match="capacity=10.0 is not a multiple"):
        dp_solve(problem)


@pytest.mark.parametrize("peak_hours", [3, 4, 5, 6])
@pytest.mark.parametrize("capacity,rate", [
    (2.0, 2.0), (4.0, 2.0), (8.0, 2.0), (10.0, 2.0), (20.0, 2.0),   # capacity sweep
    (10.0, 0.5), (10.0, 1.0), (10.0, 2.5), (10.0, 5.0),             # rate sweep
])
def test_saving_follows_the_sizing_rule(capacity, rate, peak_hours):
    """saving = min(capacity, rate * peak_hours) * spread, at any window length.

    The quantitative form of the forced-discharge result: every optimal plan
    discharges through the whole peak window and nothing else is forced, so the
    only energy that pays is what the rating can deliver inside that window.
    Capacity beyond ``rate * peak_hours`` is never discharged at the high price.

    ``peak_hours`` is swept because the whole rule turns on it, and it is the one
    quantity a reader has to supply from their own tariff.
    See docs/results/capacity-rate-sensitivity.md.
    """
    from quantum_solar import BatteryProblem

    spread, low, slots = 0.25, 0.10, 24
    # The peak ENDS at a fixed hour and grows backward, leaving the post-peak
    # refill window intact; otherwise that constraint binds instead of the rule.
    end = 20
    price = np.full(slots, low)
    price[end - peak_hours + 1:end + 1] = low + spread
    problem = BatteryProblem(
        generation=np.zeros(slots), load=np.ones(slots), price=price,
        capacity=capacity, charge_energy=rate, discharge_energy=rate,
        initial_soc=round((capacity / 2) / rate) * rate,
    )
    idle = problem.energy(np.zeros(2 * problem.num_slots, dtype=np.int8))
    saving = idle - dp_solve(problem).true_energy
    assert saving == pytest.approx(min(capacity, rate * peak_hours) * spread)


def test_all_idle_is_feasible_baseline(small_problem):
    # Doing nothing always returns to S_0; the optimum must be no worse.
    idle = np.zeros(small_problem.num_decision_vars, dtype=np.int8)
    assert small_problem.is_feasible(idle)
    assert dp_solve(small_problem).true_energy <= small_problem.energy(idle) + 1e-9
