"""Domain model: residential battery charge/discharge scheduling.

A day is split into ``T`` slots. In each slot the battery may charge (bit ``c_t``),
discharge (bit ``d_t``), or idle. Electricity is billed under time-of-use pricing
with net metering (a single price ``p_t`` for both import and export), so the grid
cost is linear in the decision bits. This module owns the *true* objective (grid
cost) and the *hard* constraints (mutual exclusion, state-of-charge bounds, and
return-to-initial-SoC); the QUBO in :mod:`quantum_solar.qubo` is a surrogate.

The QUBO variable vector always begins with the ``2T`` decision bits laid out as
``[c_0..c_{T-1}, d_0..d_{T-1}]`` followed by auxiliary slack bits. Everything here
reads only the first ``2T`` entries, so the (domain-agnostic) solvers can pass the
full vector through unchanged.

v1 assumptions: lossless battery with equal charge/discharge energy per slot
(``charge_energy == discharge_energy``), which keeps SoC on a uniform grid.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_TOL = 1e-9


@dataclass(frozen=True)
class BatteryProblem:
    """A discrete battery-scheduling instance over ``T`` time slots.

    Attributes:
        generation: ``(T,)`` solar generation per slot (kWh).
        load: ``(T,)`` household demand per slot (kWh).
        price: ``(T,)`` electricity price per slot ($/kWh, net-metered).
        capacity: usable battery capacity ``Q`` (kWh).
        charge_energy: energy added in a charging slot (kWh); v1: == discharge.
        discharge_energy: energy removed in a discharging slot (kWh).
        initial_soc: starting state of charge ``S_0`` (kWh), a multiple of the
            energy quantum within ``[0, capacity]``.
    """

    generation: np.ndarray
    load: np.ndarray
    price: np.ndarray
    capacity: float
    charge_energy: float
    discharge_energy: float
    initial_soc: float

    @property
    def num_slots(self) -> int:
        return int(self.price.shape[0])

    @property
    def num_decision_vars(self) -> int:
        return 2 * self.num_slots

    def decode(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Split a QUBO vector into charge/discharge bits ``(c, d)``."""
        x = np.asarray(x)
        t = self.num_slots
        return x[:t].astype(np.int8), x[t : 2 * t].astype(np.int8)

    def soc_trajectory(self, c: np.ndarray, d: np.ndarray) -> np.ndarray:
        """State of charge after each slot, ``S_1..S_T`` (length ``T``)."""
        delta = self.charge_energy * np.asarray(c) - self.discharge_energy * np.asarray(d)
        return self.initial_soc + np.cumsum(delta)

    def grid_cost(self, c: np.ndarray, d: np.ndarray) -> float:
        """Net-metered electricity cost of a schedule (lower is better)."""
        c = np.asarray(c, dtype=float)
        d = np.asarray(d, dtype=float)
        net = self.load - self.generation + self.charge_energy * c - self.discharge_energy * d
        return float(self.price @ net)

    def energy(self, x: np.ndarray) -> float:
        """True objective for a QUBO vector: grid cost of its decision bits."""
        c, d = self.decode(x)
        return self.grid_cost(c, d)

    def is_feasible(self, x: np.ndarray) -> bool:
        """Whether the schedule in ``x`` satisfies all hard constraints."""
        c, d = self.decode(x)
        if np.any((c == 1) & (d == 1)):
            return False  # cannot charge and discharge in the same slot
        soc = self.soc_trajectory(c, d)
        if np.any(soc < -_TOL) or np.any(soc > self.capacity + _TOL):
            return False  # SoC must stay within [0, capacity]
        return bool(abs(soc[-1] - self.initial_soc) <= _TOL)  # return to S_0


def require_soc_on_grid(problem: "BatteryProblem") -> None:
    """Raise unless ``initial_soc`` lies on the charge-energy SoC grid.

    The DP and QUBO models both reason about SoC on a grid of step
    ``charge_energy``. An ``initial_soc`` off that grid makes the DP round it
    internally, so the reported schedule can drift off-grid and exceed capacity
    (an infeasible result reported as optimal). Fail loud instead.
    """
    e = problem.charge_energy
    ratio = problem.initial_soc / e
    if abs(ratio - round(ratio)) > 1e-9:
        raise ValueError(
            f"initial_soc={problem.initial_soc} is not a multiple of "
            f"charge_energy={e}; the SoC grid would be misaligned and the "
            f"schedule can exceed capacity. Use an on-grid initial state of charge."
        )


def synthetic_instance(
    num_slots: int,
    *,
    seed: int,
    capacity: float = 3.0,
    charge_energy: float = 1.0,
    discharge_energy: float = 1.0,
    initial_soc: float = 1.0,
    noise: float = 0.05,
) -> BatteryProblem:
    """Build a reproducible instance with a plausible day cycle.

    Prices peak in the evening, solar generation peaks at midday, and load has
    morning and evening bumps. NREL/EIA-backed loaders are a future addition.
    """
    rng = np.random.default_rng(seed)
    hour = (np.arange(num_slots) + 0.5) * 24.0 / num_slots

    price = 0.10 + 0.20 * np.exp(-(((hour - 18.0) / 3.0) ** 2)) \
        + 0.05 * np.exp(-(((hour - 8.0) / 3.0) ** 2))
    generation = 2.0 * np.exp(-(((hour - 12.5) / 3.5) ** 2))
    load = 0.3 + 0.8 * np.exp(-(((hour - 7.5) / 2.0) ** 2)) \
        + 1.0 * np.exp(-(((hour - 19.0) / 2.5) ** 2))

    price = np.clip(price + noise * rng.standard_normal(num_slots), 0.01, None)
    generation = np.clip(generation + noise * rng.standard_normal(num_slots), 0.0, None)
    load = np.clip(load + noise * rng.standard_normal(num_slots), 0.0, None)

    return BatteryProblem(
        generation=generation,
        load=load,
        price=price,
        capacity=capacity,
        charge_energy=charge_energy,
        discharge_energy=discharge_energy,
        initial_soc=initial_soc,
    )
