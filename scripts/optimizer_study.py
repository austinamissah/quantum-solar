"""Can a better parameter search reach the reps=2 basin reliably?

Pre-registered in ``docs/plans/optimizer-study.md`` — read that first. Every
threshold, seed, and arm definition here is fixed by that document; nothing in
this script may be re-chosen after seeing output.

Context: at the a-priori penalty weight the reps=2 ideal mass reached mean 0.0716
(sd 0.0116, 2/6 seeds clearing) against a required 0.0781, while the observed
maximum 0.0879 *did* clear. So parameters that pass exist in the landscape and
the baseline search reaches them about a third of the time. This measures whether
any of six procedures reaches them reliably.

Reported per arm: mean, sd, and fraction-clearing — never the mean alone, because
variance is exactly what failed at the baseline.

Run::

    python scripts/optimizer_study.py [--instance-seeds 1] [--arms all]
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore")

from qiskit.circuit.library import QAOAAnsatz  # noqa: E402
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager  # noqa: E402
from qiskit_aer import AerSimulator  # noqa: E402
from qiskit_aer.primitives import EstimatorV2  # noqa: E402
from scipy.optimize import minimize  # noqa: E402

import experiment_hardware as hw  # noqa: E402
from quantum_solar import (  # noqa: E402
    Encoding,
    PenaltyWeights,
    build_qubo,
    default_weights,
    dp_solve,
    qubo_to_ising,
    synthetic_instance,
)
from quantum_solar.brute_force import enumerate_bitstrings  # noqa: E402
from quantum_solar.statevector import (  # noqa: E402
    assert_matches_qiskit,
    qaoa_probabilities,
)

# --- Fixed by the pre-registration -------------------------------------------
ALPHAS = (0.021, 0.030)
TUNING_SEEDS = tuple(range(101, 111))          # N = 10, fresh
PRIMARY_INSTANCE = 1                            # held out; sweep used seed 0
BAR = 5 / 2**6                                  # 5 x uniform at m=6 = 0.078125
RELIABLE_FRACTION = 0.8                         # >= 8/10 seeds clearing
MAXITER = 200
SPSA_ITERS = 300
ENCODING = Encoding.checkpoint(3)


def build_instance(instance_seed: int, alpha: float):
    problem = synthetic_instance(
        3, seed=instance_seed, capacity=hw.CAPACITY, charge_energy=hw.CHARGE_ENERGY,
        discharge_energy=hw.CHARGE_ENERGY, initial_soc=hw.INITIAL_SOC,
    )
    base = default_weights(problem)
    weights = PenaltyWeights(
        alpha * base.mutual_exclusion, alpha * base.soc_bounds, alpha * base.terminal
    )
    qubo = build_qubo(problem, weights, ENCODING)
    truth = dp_solve(problem)
    mask = np.array([
        problem.is_feasible(x) and abs(problem.energy(x) - truth.true_energy) < 1e-9
        for x in hw.enumerate_bitstrings(qubo.num_vars)
    ])
    return problem, qubo, mask


class Objective:
    """Shot-based and exact views of the same ``<H>``, plus an evaluation counter."""

    def __init__(self, qubo, reps: int, seed: int) -> None:
        hamiltonian, constant = qubo_to_ising(qubo)
        self.hamiltonian, self.constant = hamiltonian, constant
        self.reps = reps
        self.ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=reps)
        backend = AerSimulator(seed_simulator=seed)
        self.isa = generate_preset_pass_manager(optimization_level=1, backend=backend).run(self.ansatz)
        self.isa_hamiltonian = hamiltonian.apply_layout(self.isa.layout)
        self.estimator = EstimatorV2(options={"backend_options": {"seed_simulator": seed}})
        # QUBO energies of every basis state. `qubo_to_ising` guarantees
        # <x|H|x> + constant == qubo.energy(x), so this diagonal doubles as both
        # the cost diagonal for the NumPy statevector and the observable that
        # `exact` averages -- which is why `exact` needs no `+ constant`.
        X = enumerate_bitstrings(qubo.num_vars).astype(float)
        self.energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
        self.evaluations = 0

    def shot(self, params) -> float:
        self.evaluations += 1
        result = self.estimator.run([(self.isa, self.isa_hamiltonian, params)]).result()
        return float(result[0].data.evs) + self.constant

    def _probabilities(self, params) -> np.ndarray:
        """Exact QAOA distribution via NumPy, NOT `Statevector(QAOAAnsatz(...))`.

        The Qiskit path matrix-exponentiates the un-decomposed cost layer and
        dies with MemoryError from m=14 up. This study is pinned to m=6 by
        `build_instance`, so it never hit that ceiling -- but the ceiling is the
        reason the shared NumPy path exists, and there is no reason to keep a
        second implementation below it. A constant shift of the diagonal is a
        global phase, so the QUBO energies serve as the cost diagonal directly.
        See quantum_solar.statevector.
        """
        return qaoa_probabilities(self.energies, params, self.reps)

    def exact(self, params) -> float:
        self.evaluations += 1
        return float(self._probabilities(params) @ self.energies)

    def mass(self, params, mask) -> float:
        return float(self._probabilities(params)[mask].sum())


def spsa(cost, x0, rng, n_iter=SPSA_ITERS, a=0.2, c=0.1, alpha=0.602, gamma=0.101):
    """Standard SPSA with the Spall gain schedule."""
    x = np.array(x0, dtype=float)
    stability = 0.1 * n_iter
    for k in range(n_iter):
        ak = a / (k + 1 + stability) ** alpha
        ck = c / (k + 1) ** gamma
        delta = rng.choice([-1.0, 1.0], size=x.size)
        gradient = (cost(x + ck * delta) - cost(x - ck * delta)) / (2 * ck) / delta
        x = x - ak * gradient
    return x


def multistart(cost, n_params, rng, n_starts, method, maxiter=MAXITER):
    """Multi-start local search. ``maxiter`` caps evaluations PER RESTART.

    The default reproduces this study's pre-registered arms exactly; it is a
    parameter only so `optimizer_budget_study.py` can vary the axis this study
    held fixed, while reusing this exact code path.
    """
    best, best_cost = None, np.inf
    for _ in range(n_starts):
        x0 = rng.uniform(0.0, np.pi, size=n_params)
        res = minimize(cost, x0, method=method, options={"maxiter": maxiter})
        if res.fun < best_cost:
            best, best_cost = res.x, float(res.fun)
    return best


def run_arm(arm: str, qubo, mask, tuning_seed: int) -> tuple[float, float, int]:
    """Return (ideal optimal mass, achieved exact <H>, evaluations) for one arm/seed.

    ``<H>`` is reported at the *exact* statevector so it is comparable across arms
    regardless of whether the arm optimized a shot-based or exact objective; it is
    the achieved value, not the optimizer's own noisy estimate of it.
    """
    rng = np.random.default_rng(tuning_seed)
    obj = Objective(qubo, reps=2, seed=tuning_seed)
    n = obj.ansatz.num_parameters

    if arm.startswith("cobyla-"):
        params = multistart(obj.shot, n, rng, int(arm.split("-")[1]), "COBYLA")
    elif arm == "spsa":
        params = spsa(obj.shot, rng.uniform(0.0, np.pi, size=n), rng)
    elif arm == "lbfgs-sv":
        params = multistart(obj.exact, n, rng, 5, "L-BFGS-B")
    elif arm == "transfer":
        # reps=1 converges to the same point from every start (sd ~1e-5), so this
        # warm start is free and deterministic. Ordering is [b0,g0] -> [b0,b1,g0,g1].
        warm = Objective(qubo, reps=1, seed=tuning_seed)
        one = multistart(warm.shot, warm.ansatz.num_parameters, rng, 5, "COBYLA")
        beta, gamma_ = float(one[0]), float(one[1])
        x0 = np.array([beta, beta, gamma_, gamma_])
        params = minimize(obj.shot, x0, method="COBYLA", options={"maxiter": MAXITER}).x
        obj.evaluations += warm.evaluations
    else:
        raise ValueError(f"unknown arm {arm}")
    evaluations = obj.evaluations
    return obj.mass(params, mask), obj.exact(params), evaluations


ARMS = ("cobyla-5", "cobyla-25", "cobyla-50", "spsa", "lbfgs-sv", "transfer")

# Per-run (<H>, mass) pairs, dumped so the alignment between the objective QAOA
# minimizes and the metric the gate is on can be tested across every run and arm.
PAIRS: list[tuple] = []
PAIRS_CSV = Path(__file__).resolve().parent.parent / "docs" / "results" / "optimizer_pairs.csv"


def _dump_pairs() -> None:
    PAIRS_CSV.parent.mkdir(parents=True, exist_ok=True)
    lines = ["instance_seed,alpha,arm,tuning_seed,achieved_H,ideal_mass"]
    lines += [",".join(str(v) for v in row) for row in PAIRS]
    PAIRS_CSV.write_text("\n".join(lines) + "\n")
    print(f"wrote {len(PAIRS)} (<H>, mass) pairs to {PAIRS_CSV}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-seeds", default=str(PRIMARY_INSTANCE))
    parser.add_argument("--arms", default="all")
    args = parser.parse_args()
    arms = ARMS if args.arms == "all" else tuple(args.arms.split(","))

    print(f"bar = {BAR:.6f} (5x uniform, m=6)   tuning seeds = {list(TUNING_SEEDS)}")
    print(f"reliable = clears on >= {int(RELIABLE_FRACTION * len(TUNING_SEEDS))}/"
          f"{len(TUNING_SEEDS)} seeds", flush=True)

    # Every mass and <H> below comes from the NumPy statevector; check it against
    # Qiskit's own before reporting anything from it.
    _ref_h, _ = qubo_to_ising(build_instance(PRIMARY_INSTANCE, ALPHAS[0])[1])
    _rng = np.random.default_rng(0)
    _worst = max(assert_matches_qiskit(_ref_h, _rng.uniform(0.0, np.pi, 2 * r), r)
                 for r in (1, 2))
    print(f"statevector self-check: NumPy vs Qiskit agree to {_worst:.1e}\n", flush=True)

    for instance_seed in [int(s) for s in args.instance_seeds.split(",")]:
        role = "PRIMARY" if instance_seed == PRIMARY_INSTANCE else "robustness"
        for alpha in ALPHAS:
            _, qubo, mask = build_instance(instance_seed, alpha)
            print(f"=== instance seed {instance_seed} ({role})  alpha={alpha}  "
                  f"true-optimal states={int(mask.sum())} ===", flush=True)
            print(f"{'arm':<11} {'mean':>9} {'sd':>8} {'min':>8} {'max':>8} "
                  f"{'clears':>7} {'mean <H>':>10} {'evals':>8} {'verdict':>20}", flush=True)
            for arm in arms:
                masses, budgets, energies = [], [], []
                for tuning_seed in TUNING_SEEDS:
                    mass, energy, evaluations = run_arm(arm, qubo, mask, tuning_seed)
                    masses.append(mass)
                    energies.append(energy)
                    budgets.append(evaluations)
                    PAIRS.append((instance_seed, alpha, arm, tuning_seed, energy, mass))
                m = np.array(masses)
                clears = int((m >= BAR).sum())
                passed = m.mean() >= BAR
                reliable = clears >= RELIABLE_FRACTION * len(TUNING_SEEDS)
                verdict = ("PASS+RELIABLE" if passed and reliable
                           else "PASS (unreliable)" if passed else "fail")
                print(f"{arm:<11} {m.mean():>9.5f} {m.std():>8.5f} {m.min():>8.5f} "
                      f"{m.max():>8.5f} {clears:>4}/{len(m)} {np.mean(energies):>10.4f} "
                      f"{int(np.mean(budgets)):>8} {verdict:>20}", flush=True)
            print(flush=True)
    _dump_pairs()


if __name__ == "__main__":
    main()
