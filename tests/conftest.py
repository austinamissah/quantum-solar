"""Shared fixtures: small, deterministic problem instances."""

import numpy as np
import pytest

from quantum_solar import PenaltyWeights, SolarProblem, random_instance


@pytest.fixture
def tiny_problem() -> SolarProblem:
    """Three collinear sites, no shading, all spacings allowed.

    Yields are [1, 2, 3]; with n_panels=1 the unique optimum is site 2 (yield 3).
    """
    return SolarProblem(
        sites=np.array([[0.0, 0.0], [5.0, 0.0], [10.0, 0.0]]),
        yields=np.array([1.0, 2.0, 3.0]),
        n_panels=1,
        min_spacing=1.0,
        shading=np.zeros((3, 3)),
    )


@pytest.fixture
def tiny_weights() -> PenaltyWeights:
    return PenaltyWeights(cardinality=10.0, spacing=10.0)


@pytest.fixture
def small_problem() -> SolarProblem:
    """A 5-site instance with real shading/spacing structure for solver tests."""
    return random_instance(num_sites=5, n_panels=2, seed=7)


@pytest.fixture
def small_weights() -> PenaltyWeights:
    return PenaltyWeights(cardinality=20.0, spacing=20.0)
