"""Shared result type returned by both the classical and quantum solvers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Solution:
    """A candidate solution and its scores.

    Attributes:
        x: length-M binary decision vector for the QUBO.
        qubo_energy: value of the QUBO objective ``xᵀQx + offset`` (the quantity
            both solvers minimize).
        true_energy: the domain objective from ``problem.energy`` — independent of
            any penalty weights. Direction depends on the domain (e.g. battery
            grid cost: lower is better).
        feasible: whether ``x`` satisfies the problem's hard constraints.
    """

    x: np.ndarray
    qubo_energy: float
    true_energy: float
    feasible: bool
