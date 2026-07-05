"""Shared result type returned by both the classical and quantum solvers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Solution:
    """A candidate placement and its scores.

    Attributes:
        x: length-M binary vector; ``x[i] == 1`` means a panel is placed at site i.
        qubo_energy: value of the QUBO objective ``xᵀQx + offset`` (the quantity
            both solvers minimize).
        true_energy: physical energy yield from ``SolarProblem.energy`` (higher is
            better) — independent of any penalty weights.
        feasible: whether ``x`` satisfies the problem's hard constraints.
    """

    x: np.ndarray
    qubo_energy: float
    true_energy: float
    feasible: bool
