"""Smoke tests for the hardware run's stage (a) and stage (c) — no network.

Importing the module must not require qiskit-ibm-runtime (imported lazily in the
submit stage only), so these run in CI on the base requirements.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import experiment_hardware as hw  # noqa: E402


# --- stage (a) ---------------------------------------------------------------

def test_optimize_params_structure():
    records = hw.optimize_params(
        [{"T": 2, "seed": 0, "reps": 1}], n_starts=1, shots=256, maxiter=20
    )
    assert len(records) == 1
    r = records[0]
    assert r["T"] == 2 and r["m"] == 6
    assert len(r["params"]) == 2 * 1  # 2 angles per rep
    assert 0.0 <= r["ideal_opt_mass"] <= 1.0
    assert 0.0 <= r["ideal_feasibility"] <= 1.0
    assert np.isfinite(r["dp_cost"]) and r["stretch"] is False


# --- stage (c) helpers -------------------------------------------------------

def test_tv_distance_bounds():
    p = np.array([0.5, 0.5, 0.0, 0.0])
    q = np.array([0.0, 0.0, 0.5, 0.5])
    assert hw.tv_distance(p, p) == 0.0
    assert np.isclose(hw.tv_distance(p, q), 1.0)


def test_counts_to_probs_alignment():
    # keys are little-endian; int(key, 2) indexes bit j = qubit j.
    counts = {"00": 3, "01": 1}  # m=2: '01' -> qubit0=1 -> index 1
    probs = hw.counts_to_probs(counts, m=2)
    assert np.isclose(probs.sum(), 1.0)
    assert np.isclose(probs[0], 0.75) and np.isclose(probs[1], 0.25)


def test_exact_distribution_and_metrics_consistent():
    # Build a tiny target, take its exact distribution, and check the scalar
    # metrics are in range and the distribution normalizes.
    problem, qubo, ansatz = hw.build_target(2, 0, 1)
    rng = np.random.default_rng(0)
    params = rng.uniform(0, np.pi, size=ansatz.num_parameters)
    probs = hw.exact_distribution(ansatz, params)
    assert np.isclose(probs.sum(), 1.0)

    opt_mask, feas_mask = hw.basis_masks(problem, qubo)
    metrics = hw.scalar_metrics(probs, opt_mask, feas_mask)
    assert 0.0 <= metrics["optimal_mass"] <= 1.0
    assert 0.0 <= metrics["feasibility"] <= 1.0
    # Optimal states are a subset of feasible states.
    assert bool((~feas_mask[opt_mask]).sum() == 0)
