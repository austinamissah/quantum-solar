"""Exact enumeration correctness."""

import numpy as np
import pytest

from quantum_solar import build_qubo, brute_force_solve
from quantum_solar.brute_force import MAX_ENUMERATION_SITES, enumerate_bitstrings


def test_finds_known_optimum(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    solution = brute_force_solve(tiny_problem, qubo)

    assert np.array_equal(solution.x, [0, 0, 1])  # highest-yield single site
    assert solution.feasible
    assert solution.qubo_energy == -3.0
    assert solution.true_energy == 3.0


def test_optimum_is_feasible_and_maximizes_true_yield(small_problem, small_weights):
    qubo = build_qubo(small_problem, small_weights)
    solution = brute_force_solve(small_problem, qubo)

    assert solution.feasible
    # With adequate penalties the QUBO optimum is the best *feasible* placement.
    X = enumerate_bitstrings(small_problem.num_sites)
    feasible_true = [
        small_problem.energy(x) for x in X if small_problem.is_feasible(x)
    ]
    assert np.isclose(solution.true_energy, max(feasible_true))


def test_refuses_oversized_instances():
    from quantum_solar.qubo import QUBO

    m = MAX_ENUMERATION_SITES + 1
    oversized = QUBO(Q=np.zeros((m, m)), offset=0.0)
    with pytest.raises(ValueError, match="refusing to enumerate"):
        brute_force_solve(None, oversized)
