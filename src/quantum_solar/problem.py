"""Domain model: the true solar-panel placement problem.

This module owns the *physical* objective and the *hard* constraints. The QUBO
in :mod:`quantum_solar.qubo` is a surrogate built from this; brute force and QAOA
both minimize that surrogate, and their results are scored back against the true
objective defined here.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class SolarProblem:
    """A discrete solar-panel siting instance.

    Attributes:
        sites: ``(M, 2)`` array of candidate coordinates.
        yields: ``(M,)`` expected standalone energy yield per site (higher better).
        n_panels: exact number of panels to place (hard cardinality constraint).
        min_spacing: two selected sites closer than this are infeasible.
        shading: ``(M, M)`` symmetric, zero-diagonal matrix of pairwise yield loss
            incurred when both sites in a pair are used.
    """

    sites: np.ndarray
    yields: np.ndarray
    n_panels: int
    min_spacing: float
    shading: np.ndarray

    @property
    def num_sites(self) -> int:
        return int(self.yields.shape[0])

    def distances(self) -> np.ndarray:
        """Pairwise Euclidean distance matrix, shape ``(M, M)``."""
        delta = self.sites[:, None, :] - self.sites[None, :, :]
        return np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))

    def energy(self, x: np.ndarray) -> float:
        """True energy yield of a selection: standalone yield minus shading loss."""
        x = np.asarray(x, dtype=float)
        return float(self.yields @ x - 0.5 * x @ self.shading @ x)

    def is_feasible(self, x: np.ndarray) -> bool:
        """Whether ``x`` places exactly ``n_panels`` and respects ``min_spacing``."""
        x = np.asarray(x)
        if int(x.sum()) != self.n_panels:
            return False
        forbidden = self.distances() < self.min_spacing
        np.fill_diagonal(forbidden, False)
        selected_pairs = np.outer(x, x).astype(bool)
        np.fill_diagonal(selected_pairs, False)
        return not bool((forbidden & selected_pairs).any())


def random_instance(
    num_sites: int,
    n_panels: int,
    *,
    seed: int,
    extent: float = 10.0,
    min_spacing: float = 1.5,
    shading_radius: float = 3.0,
    shading_strength: float = 1.0,
) -> SolarProblem:
    """Build a reproducible random instance for experiments and tests.

    Sites are drawn uniformly in a square of side ``extent``. Shading decays
    linearly with distance out to ``shading_radius``.
    """
    rng = np.random.default_rng(seed)
    sites = rng.uniform(0.0, extent, size=(num_sites, 2))
    yields = rng.uniform(1.0, 5.0, size=num_sites)

    delta = sites[:, None, :] - sites[None, :, :]
    dist = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta))
    shading = shading_strength * np.clip(1.0 - dist / shading_radius, 0.0, None)
    np.fill_diagonal(shading, 0.0)

    return SolarProblem(
        sites=sites,
        yields=yields,
        n_panels=n_panels,
        min_spacing=min_spacing,
        shading=shading,
    )
