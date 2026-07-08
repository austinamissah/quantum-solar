"""Fast smoke test: the scaling experiment's core loop runs end-to-end at T=2.

Guards the experiment harness in CI without running the (minutes-long) full sweep.
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import experiment_scaling as exp  # noqa: E402


def test_experiment_core_loop_smoke():
    # Tiny settings: T=2 (6 qubits), one seed, one restart, few shots/iters.
    rows = exp.run_experiment(
        t_values=[2], seeds=[0], reps_values=[1],
        n_starts=1, shots=256, maxiter=30,
    )
    assert len(rows) == 1
    r = rows[0]

    assert r["T"] == 2 and r["m"] == 6
    assert np.isfinite(r["dp_cost"])
    assert isinstance(r["exact_match"], bool)          # value not asserted (tiny run)
    assert 0.0 <= r["opt_prob_mass"] <= 1.0
    assert 0.0 <= r["feasibility_rate"] <= 1.0
    assert r["brute_matches_dp"] is True               # T=2 has the brute cross-check
    assert r["qaoa_time_s"] >= 0.0 and r["dp_time_s"] >= 0.0


def test_csv_roundtrip(tmp_path):
    rows = exp.run_experiment(
        t_values=[2], seeds=[0], reps_values=[1],
        n_starts=1, shots=256, maxiter=30,
    )
    path = tmp_path / "r.csv"
    exp.write_csv(rows, path)
    loaded = exp.load_results(path)
    assert len(loaded) == 1
    assert loaded[0]["m"] == 6
    assert loaded[0]["brute_matches_dp"] is True


def test_uniform_baseline_exact():
    from quantum_solar import (
        brute_force_solve, build_qubo, default_weights, synthetic_instance,
    )

    problem = synthetic_instance(2, seed=0, capacity=3.0, charge_energy=1.0,
                                 initial_soc=1.0)
    qubo = build_qubo(problem, default_weights(problem))
    umass, ucost = exp.uniform_baseline(problem, qubo, shots=4096)

    # m=6 -> 64 states; exactly one optimum here -> mass = 1/64.
    assert np.isclose(umass, 1.0 / 64.0)
    # 4096 shots over 64 states almost surely samples the optimum.
    opt = brute_force_solve(problem, qubo).true_energy
    assert ucost >= opt - 1e-9 and np.isclose(ucost, opt, atol=1e-3)


def test_add_uniform_baseline_flags_below_floor():
    rows = [
        {"T": 2, "m": 6, "seed": 0, "reps": 1, "opt_prob_mass": 0.0},
        {"T": 2, "m": 6, "seed": 0, "reps": 3, "opt_prob_mass": 0.05},
    ]
    exp.add_uniform_baseline(rows, shots=4096)
    # Observed 0 -> reported as < 1/shots, ratio is an upper bound.
    assert rows[0]["mass_ratio_is_upper_bound"] is True
    assert rows[1]["mass_ratio_is_upper_bound"] is False
    assert rows[0]["shots_cover_space"] is True  # 2^6 = 64 <= 4096
