"""The DP baseline: exact, matches brute force, and scales in T."""

import time

import numpy as np

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

    # Same decisions and same cost as exhaustive enumeration of the QUBO.
    assert np.array_equal(dp.x, brute.x[: small_problem.num_decision_vars])
    assert np.isclose(dp.true_energy, brute.true_energy)


def test_dp_scales_to_full_day():
    problem = synthetic_instance(num_slots=24, seed=3)
    start = time.perf_counter()
    solution = dp_solve(problem)
    elapsed = time.perf_counter() - start

    assert solution.feasible
    assert elapsed < 1.0  # polynomial: a full day solves near-instantly


def test_all_idle_is_feasible_baseline(small_problem):
    # Doing nothing always returns to S_0; the optimum must be no worse.
    idle = np.zeros(small_problem.num_decision_vars, dtype=np.int8)
    assert small_problem.is_feasible(idle)
    assert dp_solve(small_problem).true_energy <= small_problem.energy(idle) + 1e-9
