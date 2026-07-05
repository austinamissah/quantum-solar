"""Exact classical solver — ground truth for small instances.

Enumerates all ``2^M`` bitstrings and returns the global minimizer of the QUBO
objective. This is the reference the QAOA result is checked against.
"""

from __future__ import annotations

import numpy as np

from .problem import SolarProblem
from .qubo import QUBO
from .solution import Solution

# Above this, 2^M enumeration is impractical; callers should not brute-force it.
MAX_ENUMERATION_SITES = 20


def enumerate_bitstrings(m: int) -> np.ndarray:
    """All ``2^m`` binary vectors as an ``(2^m, m)`` array (column i = bit i)."""
    idx = np.arange(2**m, dtype=np.uint64)[:, None]
    bit = np.arange(m, dtype=np.uint64)[None, :]
    return ((idx >> bit) & 1).astype(np.int8)


def brute_force_solve(problem: SolarProblem, qubo: QUBO) -> Solution:
    """Return the exact QUBO global minimizer as a scored :class:`Solution`."""
    m = qubo.num_vars
    if m > MAX_ENUMERATION_SITES:
        raise ValueError(
            f"refusing to enumerate 2^{m} states; "
            f"MAX_ENUMERATION_SITES={MAX_ENUMERATION_SITES}"
        )

    X = enumerate_bitstrings(m).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    best = int(np.argmin(energies))
    x = enumerate_bitstrings(m)[best]

    return Solution(
        x=x,
        qubo_energy=float(energies[best]),
        true_energy=problem.energy(x),
        feasible=problem.is_feasible(x),
    )
