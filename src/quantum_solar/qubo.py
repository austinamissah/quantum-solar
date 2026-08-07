"""Turn a :class:`BatteryProblem` into a QUBO.

The objective is the net-metered grid cost (linear in the decision bits); all the
quadratic structure comes from the constraint penalties:

    minimize   Σ_t p_t·(e_c·c_t − e_d·d_t)              # net-metered grid cost
             + mutual_exclusion · Σ_t c_t·d_t           # no simultaneous c & d
             + soc_bounds · <encoding penalty>          # 0 ≤ S_t ≤ Q, interior t
             + terminal · (S_T − S_0)²                  # return to initial SoC

The ``soc_bounds`` line is supplied by a pluggable :mod:`quantum_solar.encodings`
strategy; everything else here is shared by all of them. The default,
``Encoding.EXACT``, encodes ``0 ≤ S_t ≤ Q`` exactly for interior slots with a
bounded binary slack ``s_t ∈ [0, Q]``: since ``S_t`` is linear in the bits, the
penalty ``(S_t − s_t)²`` is zero iff some representable ``s_t`` equals ``S_t``,
i.e. iff ``S_t`` is in band. This is exact (preserving the brute-force
verification contract) at the cost of ``(T−1)·b`` auxiliary qubits — which is why
brute force / QAOA stay small-``T`` and the DP solver exists for scale. The
slack-free alternatives trade that exactness for a ``2T``-qubit register; see the
:mod:`quantum_solar.encodings` docstring.

Variable layout: ``[c_0..c_{T-1} | d_0..d_{T-1} | aux…]``, where the auxiliary
block is whatever the chosen encoding asks for (``(T−1)·b`` slack bits for
``Encoding.EXACT``, none for most others). Decision bits are always first, so
:meth:`BatteryProblem.energy` / ``is_feasible`` read them without knowing the
auxiliary layout.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .encodings import (
    Encoding,
    SoCEncoding,
    add_squared,
    bounded_int_weights,
    soc_terms,
)
from .problem import BatteryProblem, require_soc_on_grid

__all__ = [
    "PenaltyWeights",
    "QUBO",
    "bounded_int_weights",
    "build_qubo",
    "default_weights",
    "num_vars",
    "slack_bits_per_slot",
]


@dataclass(frozen=True)
class PenaltyWeights:
    """Lagrange multipliers turning the hard constraints into QUBO penalties."""

    mutual_exclusion: float
    soc_bounds: float
    terminal: float


@dataclass(frozen=True)
class QUBO:
    """An upper-triangular QUBO ``xᵀQx + offset``."""

    Q: np.ndarray
    offset: float

    @property
    def num_vars(self) -> int:
        return int(self.Q.shape[0])

    def energy(self, x: np.ndarray) -> float:
        x = np.asarray(x, dtype=float)
        return float(x @ self.Q @ x + self.offset)


def slack_bits_per_slot(problem: BatteryProblem) -> int:
    """Slack bits per interior slot under ``Encoding.EXACT`` (``0`` for the rest)."""
    n_max = int(round(problem.capacity / problem.charge_energy))
    return len(bounded_int_weights(n_max))


def num_vars(problem: BatteryProblem, encoding: SoCEncoding = Encoding.EXACT) -> int:
    """Qubits the QUBO will need: ``2T`` decision bits plus the encoding's aux block."""
    return 2 * problem.num_slots + encoding.aux_bits(problem)


def default_weights(problem: BatteryProblem) -> PenaltyWeights:
    """Penalty weights large enough that feasibility dominates the objective."""
    # Grid-side, so the penalties still dominate when charging imports more than it
    # stores (efficiency < 1 raises the objective's scale, never lowers it).
    e = max(problem.grid_charge_energy, problem.grid_discharge_energy)
    obj_scale = float(np.sum(np.abs(problem.price)) * e)
    lam = 10.0 * obj_scale / (e * e) + 10.0
    return PenaltyWeights(mutual_exclusion=lam, soc_bounds=lam, terminal=lam)


def build_qubo(
    problem: BatteryProblem,
    weights: PenaltyWeights,
    encoding: SoCEncoding = Encoding.EXACT,
) -> QUBO:
    """Construct the QUBO surrogate for ``problem`` under the given penalties.

    ``encoding`` selects how the interior-slot bounds ``0 ≤ S_t ≤ Q`` are
    expressed (see :mod:`quantum_solar.encodings`). The default reproduces the
    exact bounded-slack encoding; the alternatives drop the slack register for a
    ``2T``-qubit QUBO whose optimum may differ from the true one.
    """
    require_soc_on_grid(problem)
    encoding.validate(problem)
    t = problem.num_slots
    # Store-side quanta drive the SoC penalties below; the objective is priced on
    # the grid-side quanta, which is where round-trip losses enter.
    e_c = problem.charge_energy
    e_d = problem.discharge_energy
    grid_c = problem.grid_charge_energy
    grid_d = problem.grid_discharge_energy

    aux_base = 2 * t
    m = aux_base + encoding.aux_bits(problem)

    Q = np.zeros((m, m))
    offset = 0.0

    # --- Objective: net-metered grid cost (linear) ---
    for j in range(t):
        Q[j, j] += problem.price[j] * grid_c          # charging imports grid_c
        Q[t + j, t + j] += -problem.price[j] * grid_d  # discharging offsets grid_d
    offset += float(problem.price @ (problem.load - problem.generation))

    # --- Mutual exclusion: no charge & discharge in the same slot ---
    for j in range(t):
        Q[j, t + j] += weights.mutual_exclusion

    # --- SoC bounds for interior slots (pluggable) ---
    offset += encoding.add_penalty(Q, problem, weights.soc_bounds, aux_base)

    # --- Terminal constraint: return to the initial SoC ---
    # (S_T - S_0) = e·Σ(c_i - d_i): the S_0 cancels, so the constant is 0.
    offset += add_squared(Q, soc_terms(problem, t - 1), 0.0, weights.terminal)

    return QUBO(Q=Q, offset=offset)
