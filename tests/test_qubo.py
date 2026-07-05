"""Battery QUBO construction and energy correctness."""

import numpy as np

from quantum_solar import build_qubo
from quantum_solar.qubo import bounded_int_weights, slack_bits_per_slot


def test_bounded_int_weights_cover_range():
    for n_max in range(0, 17):
        weights = bounded_int_weights(n_max)
        reachable = {
            int(np.dot(bits, weights))
            for bits in np.ndindex(*([2] * len(weights)))
        }
        assert set(range(n_max + 1)) <= reachable
        assert max(reachable, default=0) == n_max


def test_feasible_energy_equals_grid_cost(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    t = tiny_problem.num_slots
    b = slack_bits_per_slot(tiny_problem)

    # Optimal schedule: charge slot 0, discharge slot 1. Slack for S_1 = 2 -> both
    # slack bits set (weights [1, 1] sum to 2).
    decision = [1, 0, 0, 1]  # c0 c1 d0 d1
    slack = [1] * ((t - 1) * b)
    x = np.array(decision + slack)

    # Penalties vanish for a feasible schedule -> QUBO energy == true grid cost.
    assert tiny_problem.is_feasible(x)
    assert np.isclose(qubo.energy(x), tiny_problem.energy(x))
    assert np.isclose(qubo.energy(x), -2.0)


def test_mutual_exclusion_term_present(tiny_problem):
    from quantum_solar import PenaltyWeights

    # Isolate the c_t·d_t coupling by zeroing the SoC/terminal squares (which also
    # contribute cross-terms to Q[j, t+j]).
    weights = PenaltyWeights(mutual_exclusion=100.0, soc_bounds=0.0, terminal=0.0)
    qubo = build_qubo(tiny_problem, weights)
    t = tiny_problem.num_slots
    for j in range(t):
        assert np.isclose(qubo.Q[j, t + j], 100.0)


def test_infeasible_costs_more_than_optimum(tiny_problem, tiny_weights):
    from quantum_solar import brute_force_solve

    qubo = build_qubo(tiny_problem, tiny_weights)
    optimum = brute_force_solve(tiny_problem, qubo).qubo_energy

    b = slack_bits_per_slot(tiny_problem)
    slack = [0] * b

    # Simultaneous charge & discharge (violates mutual exclusion).
    both = np.array([1, 0, 1, 0] + slack)
    # Never returns to S_0 (charge both slots -> S_2 = 3 > Q and != S_0).
    drift = np.array([1, 1, 0, 0] + slack)

    assert not tiny_problem.is_feasible(both)
    assert not tiny_problem.is_feasible(drift)
    assert qubo.energy(both) > optimum
    assert qubo.energy(drift) > optimum
