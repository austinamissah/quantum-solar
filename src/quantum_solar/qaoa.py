"""QAOA solver on the qiskit-aer simulator.

The variational loop is hand-rolled from :class:`QAOAAnsatz` + Aer primitives +
``scipy.optimize.minimize`` (rather than the deprecated ``qiskit_algorithms``
QAOA) so every step is explicit and testable. The circuit is transpiled for an
:class:`AerSimulator` with no coupling map, so the layout is trivial and sampled
bitstrings use standard little-endian qubit ordering.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from qiskit.circuit.library import QAOAAnsatz
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_aer import AerSimulator
from qiskit_aer.primitives import EstimatorV2, SamplerV2
from scipy.optimize import minimize

from .ising import qubo_to_ising
from .problem import BatteryProblem
from .qubo import QUBO
from .solution import Solution


@dataclass(frozen=True)
class QAOAResult(Solution):
    """A :class:`Solution` plus QAOA diagnostics."""

    optimal_params: np.ndarray
    cost_history: list[float]
    counts: dict[str, int]


def _counts_key_to_x(key: str, m: int) -> np.ndarray:
    """Convert a little-endian Qiskit bitstring to an ``x`` vector (x[i] = qubit i)."""
    bits = key.replace(" ", "")
    return np.array([int(bits[m - 1 - i]) for i in range(m)], dtype=np.int8)


class QAOASolver:
    """Solve a QUBO with QAOA on the Aer simulator."""

    def __init__(
        self,
        reps: int = 2,
        *,
        optimizer: str = "COBYLA",
        n_starts: int = 5,
        shots: int = 4096,
        seed: int | None = None,
        maxiter: int = 200,
    ) -> None:
        self.reps = reps
        self.optimizer = optimizer
        self.n_starts = n_starts
        self.shots = shots
        self.seed = seed
        self.maxiter = maxiter

    def solve(self, problem: BatteryProblem, qubo: QUBO) -> QAOAResult:
        hamiltonian, constant = qubo_to_ising(qubo)

        ansatz = QAOAAnsatz(cost_operator=hamiltonian, reps=self.reps)
        backend = AerSimulator(seed_simulator=self.seed)
        pass_manager = generate_preset_pass_manager(optimization_level=1, backend=backend)
        isa = pass_manager.run(ansatz)
        isa_hamiltonian = hamiltonian.apply_layout(isa.layout)

        estimator = EstimatorV2(options={"backend_options": {"seed_simulator": self.seed}})
        history: list[float] = []

        def cost(params: np.ndarray) -> float:
            result = estimator.run([(isa, isa_hamiltonian, params)]).result()
            value = float(result[0].data.evs) + constant
            history.append(value)
            return value

        rng = np.random.default_rng(self.seed)
        best_params: np.ndarray | None = None
        best_cost = np.inf
        for _ in range(self.n_starts):
            x0 = rng.uniform(0.0, np.pi, size=ansatz.num_parameters)
            res = minimize(
                cost, x0, method=self.optimizer, options={"maxiter": self.maxiter}
            )
            if res.fun < best_cost:
                best_cost = float(res.fun)
                best_params = res.x

        counts = self._sample(isa, best_params)
        return self._best_solution(problem, qubo, counts, best_params, history)

    def _sample(self, isa, params: np.ndarray) -> dict[str, int]:
        measured = isa.copy()
        measured.measure_all()
        sampler = SamplerV2(options={"backend_options": {"seed_simulator": self.seed}})
        result = sampler.run([(measured, params)], shots=self.shots).result()
        return result[0].data.meas.get_counts()

    def _best_solution(
        self,
        problem: BatteryProblem,
        qubo: QUBO,
        counts: dict[str, int],
        params: np.ndarray,
        history: list[float],
    ) -> QAOAResult:
        m = qubo.num_vars
        best_x: np.ndarray | None = None
        best_energy = np.inf
        for key in counts:
            x = _counts_key_to_x(key, m)
            energy = qubo.energy(x)
            if energy < best_energy:
                best_energy = energy
                best_x = x

        return QAOAResult(
            x=best_x,
            qubo_energy=float(best_energy),
            true_energy=problem.energy(best_x),
            feasible=problem.is_feasible(best_x),
            optimal_params=params,
            cost_history=history,
            counts=counts,
        )
