"""Shared fixtures: small, deterministic battery instances."""

import numpy as np
import pytest

from quantum_solar import BatteryProblem, PenaltyWeights, synthetic_instance


@pytest.fixture
def tiny_problem() -> BatteryProblem:
    """Two slots, e=1, Q=2, S_0=1, prices [1, 3], no load or solar.

    The unique optimum returning to S_0 is charge-when-cheap (slot 0) then
    discharge-when-expensive (slot 1): cost = 1·1 − 3·1 = -2.
    """
    return BatteryProblem(
        generation=np.zeros(2),
        load=np.zeros(2),
        price=np.array([1.0, 3.0]),
        capacity=2.0,
        charge_energy=1.0,
        discharge_energy=1.0,
        initial_soc=1.0,
    )


@pytest.fixture
def tiny_weights() -> PenaltyWeights:
    return PenaltyWeights(mutual_exclusion=100.0, soc_bounds=100.0, terminal=100.0)


@pytest.fixture
def small_problem() -> BatteryProblem:
    """A 3-slot instance (K=4 SoC levels) small enough to brute-force."""
    return synthetic_instance(
        num_slots=3, seed=7, capacity=3.0, charge_energy=1.0, initial_soc=1.0
    )


@pytest.fixture
def small_weights(small_problem) -> PenaltyWeights:
    from quantum_solar import default_weights

    return default_weights(small_problem)
