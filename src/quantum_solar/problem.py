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

Round-trip losses, an export credit below the import price, and asymmetric
charge/discharge energy per slot are all modeled; every one defaults to the
original v1 behavior. SoC stays on a uniform grid whose step is the greatest
common divisor of the two energy quanta (:func:`soc_quantum`).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

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
        charge_energy: energy added **to the store** in a charging slot (kWh).
        discharge_energy: energy removed **from the store** in a discharging slot.
            May differ from ``charge_energy`` — real inverters often charge and
            discharge at different rates — provided the two are commensurate; the
            SoC grid step becomes their GCD (:func:`soc_quantum`).
        initial_soc: starting state of charge ``S_0`` (kWh), a multiple of the
            energy quantum within ``[0, capacity]``.
        charge_efficiency: fraction of drawn grid energy that reaches the store,
            so a charging slot imports ``charge_energy / charge_efficiency``.
        discharge_efficiency: fraction of removed store energy that reaches the
            house, so a discharging slot offsets ``discharge_energy *
            discharge_efficiency``.

    **Losses live in the price, not in the state of charge.** The two energy quanta
    are *store-side*; the efficiencies convert to *grid-side* energy inside the
    objective only. Both default to ``1.0``, reproducing the lossless v1 model.

    SoC stays on a uniform grid of step :func:`soc_quantum` — the GCD of the two
    quanta, which is just ``charge_energy`` when they are equal. That is what the
    DP and the slack encoding need; asymmetric rates refine the grid rather than
    destroying it.
    """

    generation: np.ndarray
    load: np.ndarray
    price: np.ndarray
    capacity: float
    charge_energy: float
    discharge_energy: float
    initial_soc: float
    charge_efficiency: float = 1.0
    discharge_efficiency: float = 1.0
    sell_price: np.ndarray | None = None

    @property
    def buy_price(self) -> np.ndarray:
        """Import price ($/kWh). ``price`` is the import price; this names it."""
        return self.price

    @property
    def export_price(self) -> np.ndarray:
        """Export credit ($/kWh); ``price`` when ``sell_price`` is unset (net metering)."""
        return self.price if self.sell_price is None else self.sell_price

    @property
    def is_net_metered(self) -> bool:
        """Whether export credits at the import price, which keeps the bill linear."""
        return self.sell_price is None or bool(np.allclose(self.sell_price, self.price))

    def slot_cost(self, net: np.ndarray) -> np.ndarray:
        """Per-slot bill for a net grid draw, priced piecewise at import/export.

        Imports (``net > 0``) bill at :attr:`buy_price`; exports bill at
        :attr:`export_price`. With ``buy == sell`` this is just ``price * net`` and
        the bill is linear; once they differ it is **convex piecewise linear**, and
        the kink at ``net == 0`` is what couples the battery plan to solar and load.
        """
        net = np.asarray(net, dtype=float)
        return np.where(net > 0.0, self.buy_price, self.export_price) * net

    def action_costs(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Per-slot cost of each battery action, relative to leaving it idle.

        Returns ``(idle, charge_delta, discharge_delta, both_correction)``, each
        ``(T,)``. The household net is exogenous per slot, so a slot's cost depends
        only on which action is taken there — which is why the DP still applies
        even though the bill is no longer linear.

        ``both_correction`` is the extra cost of charging *and* discharging in one
        slot beyond the sum of the two deltas. It is zero under net metering and
        non-zero otherwise, and carrying it is what keeps the QUBO surrogate exact
        on **every** bitstring rather than only the mutually-exclusive ones (the
        brute-force contract, ``docs/ARCHITECTURE.md``).
        """
        base = self.load - self.generation
        idle = self.slot_cost(base)
        charge = self.slot_cost(base + self.grid_charge_energy) - idle
        discharge = self.slot_cost(base - self.grid_discharge_energy) - idle
        both = (self.slot_cost(base + self.grid_charge_energy - self.grid_discharge_energy)
                - idle - charge - discharge)
        return idle, charge, discharge, both

    @property
    def grid_charge_energy(self) -> float:
        """kWh imported to add ``charge_energy`` to the store (``>= charge_energy``)."""
        return self.charge_energy / self.charge_efficiency

    @property
    def grid_discharge_energy(self) -> float:
        """kWh delivered by removing ``discharge_energy`` (``<= discharge_energy``)."""
        return self.discharge_energy * self.discharge_efficiency

    @property
    def round_trip_efficiency(self) -> float:
        """Delivered energy per unit imported, ``charge_eff * discharge_eff``."""
        return self.charge_efficiency * self.discharge_efficiency

    @property
    def breakeven_price_ratio(self) -> float:
        """Peak/off-peak price ratio below which arbitrage stops paying.

        A cycle earns ``p_hi * e * eta_d`` and costs ``p_lo * e / eta_c``, so it is
        profitable exactly when ``p_hi / p_lo > 1 / round_trip_efficiency``.
        """
        return 1.0 / self.round_trip_efficiency

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
        """Electricity cost of a schedule (lower is better).

        Uses the **grid-side** quanta, so round-trip losses are charged here: a
        charging slot imports more than it stores and a discharging slot delivers
        less than it removes. At the default efficiencies of 1 both collapse to
        the store-side quanta and this is the original lossless expression.

        Exports credit at :attr:`export_price`, which equals the import price
        unless ``sell_price`` is set. See :meth:`slot_cost`.
        """
        c = np.asarray(c, dtype=float)
        d = np.asarray(d, dtype=float)
        net = (self.load - self.generation
               + self.grid_charge_energy * c - self.grid_discharge_energy * d)
        return float(self.slot_cost(net).sum())

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


MAX_SOC_LEVELS = 4096
"""Ceiling on SoC grid levels, so an awkward charge/discharge ratio fails loudly."""


def soc_quantum(problem: "BatteryProblem") -> float:
    """The SoC grid step: the largest ``g`` dividing both energy quanta exactly.

    Reachable states of charge are ``S_0 + n_c*e_c - n_d*e_d``, which lie on a
    uniform grid **iff the two quanta are commensurate** — and then the step is
    their greatest common divisor. With ``e_c == e_d`` (the v1 case) that is just
    ``e_c`` and nothing changes; asymmetric charge and discharge rates simply
    refine the grid, e.g. 2.0 kWh in and 1.5 kWh out gives ``g = 0.5`` with
    charging spanning 4 levels and discharging 3.

    Incommensurate quanta (2.0 and 2.0*sqrt(2)) have no finite grid at all — their
    reachable set is dense — and show up here as an enormous denominator, which
    :func:`require_soc_on_grid` rejects via :data:`MAX_SOC_LEVELS` rather than
    silently building an unusable state space.
    """
    charge = Fraction(problem.charge_energy).limit_denominator(10**6)
    discharge = Fraction(problem.discharge_energy).limit_denominator(10**6)
    common = math.gcd(charge.numerator * discharge.denominator,
                      discharge.numerator * charge.denominator)
    return float(Fraction(common, charge.denominator * discharge.denominator))


def require_soc_on_grid(problem: "BatteryProblem") -> None:
    """Raise unless ``initial_soc`` **and** ``capacity`` lie on the SoC grid.

    The DP and QUBO models both reason about SoC on a grid of step
    ``charge_energy``. An ``initial_soc`` off that grid makes the DP round it
    internally, so the reported schedule can drift off-grid and exceed capacity
    (an infeasible result reported as optimal). Fail loud instead.

    ``capacity`` is the top of that same grid and fails the same way: the DP takes
    ``n_max = round(capacity / e)``, which *rounds up* when the remainder exceeds
    half a step. A 10 kWh battery at 6 kWh/slot became ``n_max = 2``, i.e. a top
    level of 12 kWh — the solver returned a schedule reaching 12 kWh on a 10 kWh
    battery and reported it optimal and feasible. Checked here rather than floored
    silently, because quietly modeling a *different* battery from the one asked
    for is the same class of error.
    """
    e = soc_quantum(problem)
    for name, value in (("initial_soc", problem.initial_soc), ("capacity", problem.capacity)):
        ratio = value / e
        if abs(ratio - round(ratio)) > 1e-9:
            raise ValueError(
                f"{name}={value} is not a multiple of the SoC quantum {e} "
                f"(charge_energy={problem.charge_energy}, "
                f"discharge_energy={problem.discharge_energy}); the SoC grid would "
                f"be misaligned and the schedule can exceed capacity. "
                f"Use an on-grid {name}."
            )
    levels = round(problem.capacity / e)
    if levels > MAX_SOC_LEVELS:
        raise ValueError(
            f"charge_energy={problem.charge_energy} and "
            f"discharge_energy={problem.discharge_energy} need an SoC grid of {levels} "
            f"levels (quantum {e:g}), over the {MAX_SOC_LEVELS} cap. They are "
            f"near-incommensurate, so no practical uniform grid holds both; round "
            f"them to a common step."
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
    morning and evening bumps. For real inputs, see
    ``quantum_solar.data.load_nrel_instance``.
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
