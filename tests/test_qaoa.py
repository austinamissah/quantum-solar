"""End-to-end QAOA, checked against brute-force / DP ground truth."""

import numpy as np
import pytest

from quantum_solar import QAOASolver, build_qubo, brute_force_solve, dp_solve


@pytest.mark.slow
def test_qaoa_recovers_optimum(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    ground_truth = brute_force_solve(tiny_problem, qubo)
    dp = dp_solve(tiny_problem)
    assert np.isclose(ground_truth.true_energy, dp.true_energy)  # baselines agree

    solver = QAOASolver(reps=3, n_starts=5, shots=4096, seed=1234)
    result = solver.solve(tiny_problem, qubo)

    # The exact optimum must appear among the sampled states...
    m = qubo.num_vars
    sampled = {
        tuple(int(k.replace(" ", "")[m - 1 - i]) for i in range(m))
        for k in result.counts
    }
    assert tuple(int(b) for b in ground_truth.x) in sampled

    # ...and QAOA's best sampled schedule matches the ground-truth cost.
    assert np.isclose(result.qubo_energy, ground_truth.qubo_energy)
    assert result.feasible
    assert np.isclose(result.true_energy, -2.0)


@pytest.mark.slow
def test_qaoa_result_carries_diagnostics(tiny_problem, tiny_weights):
    qubo = build_qubo(tiny_problem, tiny_weights)
    result = QAOASolver(reps=2, n_starts=3, shots=2048, seed=0).solve(
        tiny_problem, qubo
    )

    assert result.optimal_params.shape == (4,)  # 2 reps -> 2 betas + 2 gammas
    assert len(result.cost_history) > 0
    assert sum(result.counts.values()) == 2048
