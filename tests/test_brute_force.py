"""Exact QUBO enumeration, cross-checked against the DP baseline."""

import numpy as np
import pytest

from quantum_solar import build_qubo, brute_force_solve, dp_solve
from quantum_solar.brute_force import MAX_ENUMERATION_SITES


def test_finds_known_optimum(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    solution = brute_force_solve(tiny_problem, qubo)

    c, d = tiny_problem.decode(solution.x)
    assert np.array_equal(c, [1, 0])  # charge when cheap
    assert np.array_equal(d, [0, 1])  # discharge when expensive
    assert solution.feasible
    assert np.isclose(solution.qubo_energy, -2.0)
    assert np.isclose(solution.true_energy, -2.0)


def test_qubo_optimum_matches_dp(small_problem, small_weights):
    qubo = build_qubo(small_problem, small_weights)
    brute = brute_force_solve(small_problem, qubo)
    dp = dp_solve(small_problem)

    assert brute.feasible
    # The QUBO global optimum recovers the exact (DP) minimum-cost schedule.
    assert np.isclose(brute.true_energy, dp.true_energy)


def test_refuses_oversized_instances():
    from quantum_solar.qubo import QUBO

    m = MAX_ENUMERATION_SITES + 1
    oversized = QUBO(Q=np.zeros((m, m)), offset=0.0)
    with pytest.raises(ValueError, match="refusing to enumerate"):
        brute_force_solve(None, oversized)
