"""Turn a :class:`SolarProblem` into a QUBO.

The QUBO objective is ``xᵀQx + offset`` with ``Q`` stored upper-triangular
(diagonal = linear coefficients, since ``x_i² = x_i`` for binary ``x``). It folds
the true objective together with the hard constraints expressed as weighted
penalties:

    minimize   −(true yield)                       # maximize physical yield
             + cardinality · (Σx − N)²             # place exactly N panels
             + spacing · Σ_{forbidden i<j} x_i x_j  # respect min spacing
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .problem import SolarProblem


@dataclass(frozen=True)
class PenaltyWeights:
    """Lagrange multipliers converting hard constraints into QUBO penalties."""

    cardinality: float
    spacing: float


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


def build_qubo(problem: SolarProblem, weights: PenaltyWeights) -> QUBO:
    """Construct the QUBO surrogate for ``problem`` under the given penalties."""
    m = problem.num_sites
    n = problem.n_panels
    wc = weights.cardinality
    ws = weights.spacing

    forbidden = problem.distances() < problem.min_spacing
    np.fill_diagonal(forbidden, False)

    Q = np.zeros((m, m))

    # Off-diagonal (i < j): shading loss, cardinality cross term (2·wc from the
    # square), and the spacing penalty on forbidden pairs.
    off = np.triu(problem.shading + 2.0 * wc + ws * forbidden, k=1)
    Q += off

    # Diagonal: −yield (maximize) plus the linear part of (Σx − N)².
    diag = -problem.yields + wc * (1.0 - 2.0 * n)
    np.fill_diagonal(Q, diag)

    offset = wc * n * n
    return QUBO(Q=Q, offset=offset)
