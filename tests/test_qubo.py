"""QUBO construction and energy correctness."""

import numpy as np

from quantum_solar import build_qubo


def test_energy_matches_hand_computation(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)

    # Diagonal: -yield + wc*(1 - 2N) = -yield - 10 (N=1, wc=10).
    assert np.allclose(np.diag(qubo.Q), [-11.0, -12.0, -13.0])
    # Off-diagonal: 2*wc = 20 for every pair (no shading, no forbidden pairs).
    assert qubo.Q[0, 1] == 20.0 and qubo.Q[0, 2] == 20.0 and qubo.Q[1, 2] == 20.0
    # Offset: wc * N^2 = 10.
    assert qubo.offset == 10.0

    # Feasible single-panel picks: energy == -yield.
    assert qubo.energy([0, 0, 1]) == -3.0
    assert qubo.energy([1, 0, 0]) == -1.0
    # Empty selection pays the full cardinality penalty.
    assert qubo.energy([0, 0, 0]) == 10.0


def test_infeasible_costs_more_than_optimum(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    optimum = qubo.energy([0, 0, 1])  # exactly one panel
    # Every wrong-cardinality selection must be strictly worse.
    for x in ([1, 1, 0], [1, 1, 1], [0, 0, 0], [1, 0, 1]):
        assert qubo.energy(x) > optimum


def test_spacing_penalty_applies_to_close_pairs(tiny_weights):
    from quantum_solar import SolarProblem

    # Sites 0 and 1 are closer than min_spacing -> forbidden pair.
    problem = SolarProblem(
        sites=np.array([[0.0, 0.0], [0.5, 0.0], [10.0, 0.0]]),
        yields=np.array([1.0, 1.0, 1.0]),
        n_panels=2,
        min_spacing=1.0,
        shading=np.zeros((3, 3)),
    )
    qubo = build_qubo(problem, tiny_weights)
    # The forbidden pair carries the extra spacing penalty; a far pair does not.
    assert qubo.Q[0, 1] == 20.0 + 10.0  # 2*wc + ws
    assert qubo.Q[0, 2] == 20.0
