"""Annualized battery savings: exact per-day DP over a full calendar year.

The return-to-initial-SoC constraint (``S_T = S_0``) makes days independent — a
battery that ends each day where it started cannot shift energy across the day
boundary — so the annual optimum is exactly the sum of 365 independent single-day
optima. There is no need for a coupled 365-day optimization; we solve each day
with the exact DP (:func:`~quantum_solar.dp_solve`, microseconds per day) and sum.

Coherence and cost come from the same real inputs as :func:`load_nrel_instance`,
assembled per day via the shared :func:`~quantum_solar.data.build_instance`
factory: PVWatts generation (fetched once as 8760 hourly values), the URDB price
schedule for each day's month and weekday/weekend type, and the ResStock load
bucket for the day's (season, day type). Days are classified under the pinned
AMY-2018 calendar (:mod:`quantum_solar.data.calendar`), which is non-leap so
``range(365)`` aligns 1:1 with the 8760-hour array.

Zero extra API calls beyond a single-day load: PVWatts is fetched once and the
URDB schedule is memoized per ``(month, weekend)`` (at most a handful of distinct
fetches), all served from the same on-disk cache.

QAOA stays out of the annual path — it is validated against the DP separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from .data.calendar import day_to_month, day_type, is_weekend
from .data.load_profile import load_profile
from .data.nrel import (
    DEFAULT_CACHE,
    XCEL_CO_RETOU_LABEL,
    build_instance,
    fetch_pvwatts,
    fetch_urdb_tou,
    price_to_slots,
    to_slots,
)
from .dynamic_programming import dp_solve

_NUM_SLOTS = 24  # v1: hourly only (see load_nrel_instance)


@dataclass(frozen=True)
class DayResult:
    """One day's exact costs and the three-way counterfactual split (dollars).

    The three grid-cost legs isolate what each system contributes, so savings are
    unambiguously attributable:

        no_system_cost   = price @ load                 (no solar, no battery)
        solar_only_cost  = price @ (load - generation)  (solar, battery idle)
        optimized_cost   = solar + DP-optimal battery

        solar_savings    = no_system_cost - solar_only_cost   (>= 0)
        battery_savings  = solar_only_cost - optimized_cost   (>= 0)

    ``battery_savings`` holds solar fixed, so it is the value of the battery
    *alone* — not conflated with the solar contribution.

    Attributes:
        day: 0-based day-of-year (AMY 2018).
        month: 0-based month.
        day_type: ``"weekday"`` or ``"weekend"``.
    """

    day: int
    month: int
    day_type: str
    no_system_cost: float
    solar_only_cost: float
    optimized_cost: float
    solar_savings: float
    battery_savings: float


@dataclass(frozen=True)
class AnnualResult:
    """Annual totals (the three-way split) plus the per-day breakdown."""

    days: tuple[DayResult, ...]
    no_system_cost: float      # annual bill: no solar, no battery ($)
    solar_only_cost: float     # annual bill: solar, battery idle ($)
    optimized_cost: float      # annual bill: solar + optimal battery ($)
    solar_savings: float       # no_system - solar_only ($/year)
    battery_savings: float     # solar_only - optimized ($/year); battery alone


def annual_savings(
    lat: float,
    lon: float,
    *,
    days: Iterable[int] | None = None,
    capacity: float = 10.0,
    charge_energy: float = 2.0,
    discharge_energy: float | None = None,
    initial_soc: float | None = None,
    system_kw: float = 5.0,
    rate_label: str = XCEL_CO_RETOU_LABEL,
    cache_dir: Path | None = DEFAULT_CACHE,
    api_key: str | None = None,
) -> AnnualResult:
    """Exact annualized battery savings for a household at ``lat``/``lon``.

    Solves every day in ``days`` (default the full year, 0..364) independently with
    the exact DP and sums. Battery parameters mirror :func:`load_nrel_instance`.
    """
    # Fetch generation once (8760 hourly kWh); memoize each price schedule per
    # (month, weekend) so no fetch repeats across the year.
    hourly_generation = fetch_pvwatts(lat, lon, system_kw, cache_dir=cache_dir, api_key=api_key)
    price_cache: dict[tuple[int, bool], np.ndarray] = {}

    def price_for(month: int, weekend: bool) -> np.ndarray:
        key = (month, weekend)
        if key not in price_cache:
            hourly_price = fetch_urdb_tou(
                rate_label, month=month, weekend=weekend, cache_dir=cache_dir, api_key=api_key
            )
            price_cache[key] = price_to_slots(hourly_price, _NUM_SLOTS)
        return price_cache[key]

    return annual_from_inputs(
        hourly_generation, price_for, load_profile,
        days=days,
        capacity=capacity,
        charge_energy=charge_energy,
        discharge_energy=discharge_energy,
        initial_soc=initial_soc,
    )


def annual_from_inputs(
    hourly_generation: np.ndarray,
    price_for,
    load_for,
    *,
    days: Iterable[int] | None = None,
    capacity: float = 10.0,
    charge_energy: float = 2.0,
    discharge_energy: float | None = None,
    initial_soc: float | None = None,
) -> AnnualResult:
    """I/O-free core of the annual loop, from already-resolved inputs.

    Both :func:`annual_savings` (live fetchers) and offline consumers (a committed
    snapshot, e.g. ``scripts/annual_savings.py``) call this, so the three-way
    attribution is computed in exactly one place and cannot drift between them.

    Args:
        hourly_generation: ``(8760,)`` hourly generation (kWh); day ``d`` reads
            hours ``24d..24d+24``.
        price_for: ``(month, weekend) -> (24,)`` per-slot price ($/kWh).
        load_for: ``(month, day_type) -> (24,)`` hourly load (kWh).
        days: which 0-based days-of-year to solve (default the full year).
    """
    days = range(365) if days is None else list(days)

    results: list[DayResult] = []
    for day in days:
        month = day_to_month(day)
        weekend = is_weekend(day)
        dtype = day_type(day)

        generation = to_slots(hourly_generation, day, _NUM_SLOTS)
        price = price_for(month, weekend)
        load = to_slots(load_for(month, dtype), day=0, num_slots=_NUM_SLOTS)

        problem = build_instance(
            generation, load, price,
            capacity=capacity,
            charge_energy=charge_energy,
            discharge_energy=discharge_energy,
            initial_soc=initial_soc,
        )
        zero = np.zeros(_NUM_SLOTS, dtype=np.int8)
        no_system = float(problem.price @ problem.load)   # no solar, no battery
        solar_only = problem.grid_cost(zero, zero)        # solar, battery idle: price @ (load - gen)
        optimized = dp_solve(problem).true_energy         # solar + DP-optimal battery
        results.append(DayResult(
            day=day,
            month=month,
            day_type=dtype,
            no_system_cost=no_system,
            solar_only_cost=solar_only,
            optimized_cost=optimized,
            solar_savings=no_system - solar_only,
            battery_savings=solar_only - optimized,
        ))

    no_system_total = float(sum(r.no_system_cost for r in results))
    solar_only_total = float(sum(r.solar_only_cost for r in results))
    optimized_total = float(sum(r.optimized_cost for r in results))
    return AnnualResult(
        days=tuple(results),
        no_system_cost=no_system_total,
        solar_only_cost=solar_only_total,
        optimized_cost=optimized_total,
        solar_savings=no_system_total - solar_only_total,
        battery_savings=solar_only_total - optimized_total,
    )
