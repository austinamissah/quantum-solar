"""Turn a :class:`BatteryProblem` into a QUBO.

The objective is the net-metered grid cost (linear in the decision bits); all the
quadratic structure comes from the constraint penalties:

    minimize   Σ_t p_t·(e_c·c_t − e_d·d_t)              # net-metered grid cost
             + mutual_exclusion · Σ_t c_t·d_t           # no simultaneous c & d
             + soc_bounds · Σ_{t<T} (S_t − s_t)²        # 0 ≤ S_t ≤ Q via slack
             + terminal · (S_T − S_0)²                  # return to initial SoC

The SoC inequality ``0 ≤ S_t ≤ Q`` is encoded exactly for interior slots with a
bounded binary slack ``s_t ∈ [0, Q]``: since ``S_t`` is linear in the bits, the
penalty ``(S_t − s_t)²`` is zero iff some representable ``s_t`` equals ``S_t``,
i.e. iff ``S_t`` is in band. This is exact (preserving the brute-force
verification contract) at the cost of ``(T−1)·b`` auxiliary qubits — which is why
brute force / QAOA stay small-``T`` and the DP solver exists for scale.

Variable layout: ``[c_0..c_{T-1} | d_0..d_{T-1} | slack_0..slack_{T-2}]``, each
interior slot contributing ``b`` slack bits. Decision bits are first, so
:meth:`BatteryProblem.energy` / ``is_feasible`` read them without knowing the
slack layout.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .problem import BatteryProblem, require_soc_on_grid


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


def bounded_int_weights(n_max: int) -> list[int]:
    """Binary weights that represent every integer in ``[0, n_max]`` exactly.

    Uses powers of two with an adjusted final coefficient so the maximum is
    exactly ``n_max`` (the standard bounded-integer encoding).
    """
    if n_max <= 0:
        return []
    m = int(np.floor(np.log2(n_max)))
    weights = [1 << i for i in range(m)]
    weights.append(n_max - (2**m - 1))
    return weights


def slack_bits_per_slot(problem: BatteryProblem) -> int:
    n_max = int(round(problem.capacity / problem.charge_energy))
    return len(bounded_int_weights(n_max))


def default_weights(problem: BatteryProblem) -> PenaltyWeights:
    """Penalty weights large enough that feasibility dominates the objective."""
    e = max(problem.charge_energy, problem.discharge_energy)
    obj_scale = float(np.sum(np.abs(problem.price)) * e)
    lam = 10.0 * obj_scale / (e * e) + 10.0
    return PenaltyWeights(mutual_exclusion=lam, soc_bounds=lam, terminal=lam)


def _add_squared(Q: np.ndarray, terms: list[tuple[int, float]], const: float, weight: float) -> float:
    """Accumulate ``weight·(Σ α_i x_i + const)²`` into upper-triangular ``Q``.

    Returns the scalar contribution to the QUBO offset.
    """
    for i, ai in terms:
        Q[i, i] += weight * (ai * ai + 2.0 * const * ai)
    for a in range(len(terms)):
        i, ai = terms[a]
        for b in range(a + 1, len(terms)):
            j, aj = terms[b]
            lo, hi = (i, j) if i < j else (j, i)
            Q[lo, hi] += weight * 2.0 * ai * aj
    return weight * const * const


def build_qubo(problem: BatteryProblem, weights: PenaltyWeights) -> QUBO:
    """Construct the QUBO surrogate for ``problem`` under the given penalties."""
    require_soc_on_grid(problem)
    t = problem.num_slots
    e_c = problem.charge_energy
    e_d = problem.discharge_energy
    e = e_c  # SoC grid step (v1: e_c == e_d)

    slot_weights = bounded_int_weights(int(round(problem.capacity / e)))
    b = len(slot_weights)
    m = 2 * t + (t - 1) * b
    slack_base = 2 * t

    Q = np.zeros((m, m))
    offset = 0.0

    # --- Objective: net-metered grid cost (linear) ---
    for j in range(t):
        Q[j, j] += problem.price[j] * e_c          # charging imports e_c
        Q[t + j, t + j] += -problem.price[j] * e_d  # discharging exports e_d
    offset += float(problem.price @ (problem.load - problem.generation))

    # --- Mutual exclusion: no charge & discharge in the same slot ---
    for j in range(t):
        Q[j, t + j] += weights.mutual_exclusion

    def soc_terms(upto: int) -> list[tuple[int, float]]:
        # S after slot `upto` (0-based) as a linear form in the decision bits.
        return [(i, e_c) for i in range(upto + 1)] + [(t + i, -e_d) for i in range(upto + 1)]

    # --- SoC bounds for interior slots via bounded slack ---
    for j in range(t - 1):
        terms = list(soc_terms(j))
        for k, w in enumerate(slot_weights):
            terms.append((slack_base + j * b + k, -e * w))
        offset += _add_squared(Q, terms, problem.initial_soc, weights.soc_bounds)

    # --- Terminal constraint: return to the initial SoC ---
    # (S_T - S_0) = e·Σ(c_i - d_i): the S_0 cancels, so the constant is 0.
    offset += _add_squared(Q, soc_terms(t - 1), 0.0, weights.terminal)

    return QUBO(Q=Q, offset=offset)
