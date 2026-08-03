"""Does the penalty weight, not the encoding, limit QAOA's concentration?

``default_weights`` sizes penalties at ~10x the objective scale so that
feasibility dominates — which is correct for the *classical* QUBO, where any
feasible-but-suboptimal state must lose to the optimum. But QAOA minimizes
``<H>``, and at T=3 the penalty scale is 14.81 against an objective span of 0.31
across the feasible set: a 48x ratio that makes the cost nearly invisible. The
observed consequence is that reps=2 reaches a far lower ``<H>`` than reps=1
(1.14 vs 16.08) while putting *less* mass on the optimum (0.0002 vs 0.0453) — it
spends its expressivity on feasibility (93.6% vs 29.2%), because that is what
``<H>`` rewards.

This sweep scales all three penalties by ``alpha`` and reports, at each depth:

- **ideal mass (argmin)** — mass on the QUBO's own ground state,
- **ideal mass (true)** — mass on the *true* optimum, which diverges from the
  above once ``alpha`` is small enough that the surrogate's optimum stops being
  feasible; without this column a small ``alpha`` can look like a win while
  concentrating on the wrong state,
- **feasible mass**, and **achieved <H>**.

``qubo_min_exact`` supplies the ground truth for whether the surrogate's optimum
is still the real one, so the sweep can distinguish "the weight helped" from "the
weight broke the encoding".

Run::

    python scripts/weight_sweep.py [--slots 3] [--alphas 0.003,0.01,...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qiskit.circuit.library import QAOAAnsatz  # noqa: E402
from qiskit.quantum_info import Statevector  # noqa: E402

import experiment_hardware as hw  # noqa: E402
from quantum_solar import (  # noqa: E402
    Encoding,
    PenaltyWeights,
    QAOASolver,
    build_qubo,
    default_weights,
    dp_solve,
    qubo_to_ising,
    synthetic_instance,
)
from quantum_solar.qubo_search import qubo_min_exact  # noqa: E402

DEFAULT_ALPHAS = "0.003,0.01,0.03,0.1,0.3,1.0,3.0"


def scaled(problem, alpha: float) -> PenaltyWeights:
    base = default_weights(problem)
    return PenaltyWeights(
        mutual_exclusion=alpha * base.mutual_exclusion,
        soc_bounds=alpha * base.soc_bounds,
        terminal=alpha * base.terminal,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slots", type=int, default=3)
    parser.add_argument("--alphas", default=DEFAULT_ALPHAS)
    args = parser.parse_args()

    t = args.slots
    problem = synthetic_instance(
        t, seed=0, capacity=hw.CAPACITY, charge_energy=hw.CHARGE_ENERGY,
        discharge_energy=hw.CHARGE_ENERGY, initial_soc=hw.INITIAL_SOC,
    )
    encoding = Encoding.checkpoint(3)
    truth = dp_solve(problem)

    m = build_qubo(problem, default_weights(problem), encoding).num_vars
    X = hw.enumerate_bitstrings(m)
    true_opt = np.array(
        [problem.is_feasible(x) and abs(problem.energy(x) - truth.true_energy) < 1e-9
         for x in X]
    )
    uniform = 1.0 / 2**m
    print(f"T={t} encoding=checkpoint(3) m={m}  uniform={uniform:.5f}  "
          f"5x-uniform bar={5 * uniform:.5f}  true-optimal states={int(true_opt.sum())}\n")

    header = (f"{'alpha':>7} {'surrogate':>10} {'reps':>5} {'<H>':>10} "
              f"{'mass(argmin)':>13} {'mass(true)':>11} {'x unif':>7} {'feas':>7}")
    print(header)
    print("-" * len(header))
    for alpha in [float(a) for a in args.alphas.split(",")]:
        weights = scaled(problem, alpha)
        qubo = build_qubo(problem, weights, encoding)
        exact = qubo_min_exact(problem, weights, encoding)
        ok = exact.feasible and abs(exact.true_energy - truth.true_energy) < 1e-9
        verdict = "optimal" if ok else ("feasible" if exact.feasible else "INFEASIBLE")

        Xf = X.astype(float)
        energies = np.einsum("bi,ij,bj->b", Xf, qubo.Q, Xf) + qubo.offset
        argmin_mask = np.isclose(energies, energies.min(), atol=1e-6)
        _, feas_mask = hw.basis_masks(problem, qubo)
        hamiltonian, _ = qubo_to_ising(qubo)

        for reps in (1, 2):
            res = QAOASolver(reps=reps, n_starts=hw.N_STARTS, shots=hw.SHOTS,
                             seed=hw.QAOA_SEED, maxiter=hw.MAXITER).solve(problem, qubo)
            ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=reps)
            probs = Statevector(
                ansatz.assign_parameters(list(res.optimal_params))
            ).probabilities()
            mass_true = float(probs[true_opt].sum())
            print(f"{alpha:>7.3f} {verdict:>10} {reps:>5} {float(probs @ energies):>10.4f} "
                  f"{float(probs[argmin_mask].sum()):>13.5f} {mass_true:>11.5f} "
                  f"{mass_true / uniform:>7.2f} {float(probs[feas_mask].sum()):>7.4f}")
        print()


if __name__ == "__main__":
    main()
