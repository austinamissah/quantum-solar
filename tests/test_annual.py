"""Annual savings loop: aggregation, per-day independence, and the invariants
that justify the modeling choices (per-day decoupling, $0 flat-price arbitrage,
load-invariant savings)."""

import numpy as np
import pytest

from quantum_solar import annual_savings, dp_solve
from quantum_solar import annual as annual_mod
from quantum_solar.annual import AnnualResult
from quantum_solar.data import build_instance, load_profile
from quantum_solar.data import nrel


# --- fixtures: real inputs replaced by deterministic offline stubs -----------

def _synthetic_hourly_generation() -> np.ndarray:
    # 8760 hourly kWh: a midday solar bump repeated every day (varies by hour, not day).
    hour = np.arange(24)
    day_curve = 2.0 * np.exp(-(((hour - 12.5) / 3.5) ** 2))
    return np.tile(day_curve, 365)


def _tou_price24() -> np.ndarray:
    price = np.full(24, 0.13)
    price[17:21] = 0.38  # evening on-peak, like the real RE-TOU summer weekday
    return price


def _install_stubs(monkeypatch, *, price24=None, flat_weekend=True):
    """Patch the real-data fetchers with offline stubs.

    Patch in the ``annual`` namespace — annual.py imports these names directly, so
    that is where they are looked up (patching ``nrel.*`` would not take effect).
    """
    gen = _synthetic_hourly_generation()
    monkeypatch.setattr(annual_mod, "fetch_pvwatts", lambda *a, **k: gen)

    weekday_price = _tou_price24() if price24 is None else price24

    def urdb(label, *, month, weekend, cache_dir=None, api_key=None):
        if weekend and flat_weekend:
            return np.full(24, 0.13)  # weekends flat off-peak (no arbitrage)
        return weekday_price

    monkeypatch.setattr(annual_mod, "fetch_urdb_tou", urdb)
    return gen, weekday_price


# --- aggregation + per-day independence (S_T = S_0 decoupling) ----------------

def test_annual_total_equals_sum_of_independent_day_solves(monkeypatch):
    _, weekday_price = _install_stubs(monkeypatch)
    days = [0, 172, 200, 5, 364]  # mix of seasons and weekday/weekend
    result = annual_savings(39.7, -105.2, days=days, cache_dir=None, api_key="x")

    assert isinstance(result, AnnualResult)
    assert len(result.days) == len(days)

    # Rebuild each day independently and solve it in isolation: the annual totals
    # must equal the sum of standalone per-day DP costs. This is the decoupling the
    # return-to-initial-SoC constraint buys — days do not interact.
    gen = _synthetic_hourly_generation()
    indep_opt = 0.0
    indep_solar = 0.0
    for dr in result.days:
        hourly_price = np.full(24, 0.13) if dr.day_type == "weekend" else weekday_price
        price = nrel.price_to_slots(hourly_price, 24)
        load = load_profile(dr.month, dr.day_type)
        problem = build_instance(nrel.to_slots(gen, dr.day, 24), load, price)
        zero = np.zeros(24, dtype=np.int8)
        indep_solar += problem.grid_cost(zero, zero)
        indep_opt += dp_solve(problem).true_energy
        # three-way legs are ordered and savings are exact, non-negative differences
        assert dr.no_system_cost >= dr.solar_only_cost - 1e-9  # solar never costs more
        assert np.isclose(dr.solar_savings, dr.no_system_cost - dr.solar_only_cost)
        assert np.isclose(dr.battery_savings, dr.solar_only_cost - dr.optimized_cost)
        assert dr.battery_savings >= -1e-9

    assert np.isclose(result.optimized_cost, indep_opt)
    assert np.isclose(result.solar_only_cost, indep_solar)
    assert np.isclose(result.battery_savings, indep_solar - indep_opt)


def test_full_year_runs_over_365_days(monkeypatch):
    _install_stubs(monkeypatch)
    result = annual_savings(39.7, -105.2, cache_dir=None, api_key="x")
    assert len(result.days) == 365
    assert {r.day for r in result.days} == set(range(365))
    assert result.battery_savings > 0.0  # a real TOU spread yields positive savings


# --- invariant: a flat-price day yields exactly $0 battery savings ------------

def test_flat_price_day_yields_zero_savings(monkeypatch):
    # Every day (weekday and weekend) sees a perfectly flat price -> no arbitrage.
    _install_stubs(monkeypatch, price24=np.full(24, 0.15), flat_weekend=True)
    result = annual_savings(39.7, -105.2, days=range(20), cache_dir=None, api_key="x")

    for dr in result.days:
        assert np.isclose(dr.battery_savings, 0.0)
    assert np.isclose(result.battery_savings, 0.0)


def test_real_weekend_is_flat_so_weekend_savings_zero(monkeypatch):
    _install_stubs(monkeypatch)  # weekdays TOU, weekends flat
    result = annual_savings(39.7, -105.2, cache_dir=None, api_key="x")
    weekend_savings = [r.battery_savings for r in result.days if r.day_type == "weekend"]
    assert weekend_savings and all(np.isclose(s, 0.0) for s in weekend_savings)


# --- invariant: perturbing load moves the bill but not the battery savings ----

def test_load_perturbation_leaves_savings_unchanged(monkeypatch):
    # This is the property that justifies coarse (2-bucket) load profiles: under
    # net metering the price*load term is a decision-free constant, so it shifts
    # both baseline and optimized cost equally and cancels in the savings.
    days = list(range(30))
    _install_stubs(monkeypatch)
    base = annual_savings(39.7, -105.2, days=days, cache_dir=None, api_key="x")

    # Add an arbitrary per-hour bump to every load bucket and re-run.
    bump = np.linspace(0.5, 1.5, 24)

    def perturbed(month, day_type):
        return load_profile(month, day_type) + bump

    monkeypatch.setattr(annual_mod, "load_profile", perturbed)
    perturbed_result = annual_savings(39.7, -105.2, days=days, cache_dir=None, api_key="x")

    # Both savings legs are load-invariant; only the bill levels move.
    assert np.isclose(perturbed_result.battery_savings, base.battery_savings)
    assert np.isclose(perturbed_result.solar_savings, base.solar_savings)
    for a, b in zip(base.days, perturbed_result.days):
        assert np.isclose(a.battery_savings, b.battery_savings)
    assert perturbed_result.solar_only_cost > base.solar_only_cost
    # price*load shifts every leg by the same amount, so all differences match.
    shift = perturbed_result.solar_only_cost - base.solar_only_cost
    assert np.isclose(perturbed_result.optimized_cost - base.optimized_cost, shift)
    assert np.isclose(perturbed_result.no_system_cost - base.no_system_cost, shift)
