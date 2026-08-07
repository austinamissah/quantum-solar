"""Export credited below import: the bill stops being linear.

Under net metering the bill is ``price @ net`` and separates into a household term
and a battery term. Once export credits below import it is **convex piecewise
linear** with a kink at ``net == 0``, and that kink is what finally couples the
battery plan to solar and load — the thing round-trip losses were wrongly expected
to do.

Two things need guarding. The DP must still be valid (it is: the household net is
exogenous, so cost is still per-(slot, action)), and the QUBO must stay exact on
*every* bitstring, which needs a ``c_j*d_j`` correction that is identically zero
under net metering.
"""

from __future__ import annotations

import itertools

import numpy as np
import pytest

from quantum_solar import (
    BatteryProblem,
    PenaltyWeights,
    brute_force_solve,
    build_qubo,
    default_weights,
    dp_solve,
    synthetic_instance,
)
from quantum_solar.qubo_search import qubo_min_exact

RATIOS = [1.0, 0.6, 0.3, 0.0]


def with_export(problem: BatteryProblem, ratio: float, **kw) -> BatteryProblem:
    """Same instance with export credited at ``ratio`` of the import price."""
    fields = dict(
        generation=problem.generation, load=problem.load, price=problem.price,
        capacity=problem.capacity, charge_energy=problem.charge_energy,
        discharge_energy=problem.discharge_energy, initial_soc=problem.initial_soc,
        charge_efficiency=problem.charge_efficiency,
        discharge_efficiency=problem.discharge_efficiency,
        sell_price=problem.price * ratio,
    )
    fields.update(kw)
    return BatteryProblem(**fields)


def test_net_metering_is_the_default_and_stays_linear():
    problem = synthetic_instance(4, seed=0)
    assert problem.sell_price is None
    assert problem.is_net_metered
    assert np.allclose(problem.export_price, problem.buy_price)
    # The c*d correction vanishes exactly, so the QUBO keeps its linear objective.
    _, _, _, both = problem.action_costs()
    assert np.allclose(both, 0.0)


def test_export_ratio_one_is_indistinguishable_from_net_metering():
    base = synthetic_instance(5, seed=1, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    assert with_export(base, 1.0).is_net_metered
    assert dp_solve(with_export(base, 1.0)).true_energy == pytest.approx(
        dp_solve(base).true_energy)


@pytest.mark.parametrize("ratio", RATIOS)
def test_slot_cost_is_piecewise(ratio):
    problem = with_export(synthetic_instance(3, seed=0), ratio)
    net = np.array([2.0, -2.0, 0.0])
    got = problem.slot_cost(net)
    assert got[0] == pytest.approx(problem.buy_price[0] * 2.0)      # import at buy
    assert got[1] == pytest.approx(problem.export_price[1] * -2.0)  # export at sell
    assert got[2] == 0.0


@pytest.mark.parametrize("ratio", RATIOS)
@pytest.mark.parametrize("seed", [0, 2, 5])
def test_dp_matches_brute_force_with_export_pricing(ratio, seed):
    """The load-bearing cross-check, now with a non-linear bill.

    Exercises `slot_cost`, `action_costs`, the DP recurrence and `build_qubo`'s
    objective (including the c*d correction) at once.
    """
    base = synthetic_instance(4, seed=seed, capacity=3.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=1.0)
    problem = with_export(base, ratio)
    qubo = build_qubo(problem, default_weights(problem))
    brute = brute_force_solve(problem, qubo)
    dp = dp_solve(problem)
    assert brute.feasible and dp.feasible
    assert dp.true_energy == pytest.approx(brute.true_energy)


@pytest.mark.parametrize("ratio", RATIOS)
def test_qubo_is_exact_on_every_bitstring_including_infeasible_ones(ratio):
    """`<x|Qx> + offset == problem.energy(x)` for ALL x, not just feasible ones.

    This is what the ``c_j*d_j`` correction buys. Without it the surrogate is right
    on mutually-exclusive assignments and silently wrong on ``c_j == d_j == 1``,
    which brute force does enumerate — so the encoding contract would break exactly
    where nothing looks at it.
    """
    base = synthetic_instance(3, seed=4, capacity=2.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=1.0)
    problem = with_export(base, ratio)
    t = problem.num_slots
    # Zero penalties, so what remains is exactly the objective. Slack bits are left
    # at zero: the objective never references them, only the penalties do.
    plain = build_qubo(problem, PenaltyWeights(0.0, 0.0, 0.0))
    for bits in itertools.product((0, 1), repeat=2 * t):
        x = np.zeros(plain.num_vars, dtype=np.int8)
        x[:2 * t] = bits
        c, d = x[:t], x[t:2 * t]
        assert plain.energy(x) == pytest.approx(problem.grid_cost(c, d))


@pytest.mark.parametrize("ratio", [1.0, 0.5, 0.0])
def test_qubo_search_matches_dp_with_export_pricing(ratio):
    base = synthetic_instance(5, seed=3, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    problem = with_export(base, ratio)
    got = qubo_min_exact(problem, default_weights(problem))
    assert got.feasible
    assert got.true_energy == pytest.approx(dp_solve(problem).true_energy)


def test_export_below_import_couples_the_plan_to_solar():
    """The claim losses could not deliver: now the household changes the plan.

    With a kink at ``net == 0`` it matters whether the house is importing or
    exporting in a slot, and that depends on solar and load — so the optimal
    battery plan stops being a function of the price curve alone.
    """
    from quantum_solar.dynamic_programming import optima_census

    price = np.full(12, 0.30)
    price[7:10] = 0.60
    load = np.ones(12)
    heavy_solar = np.zeros(12)
    heavy_solar[2:6] = 6.0          # big midday export window

    def plan(generation, ratio):
        problem = BatteryProblem(
            generation=generation, load=load, price=price, capacity=4.0,
            charge_energy=1.0, discharge_energy=1.0, initial_soc=2.0,
            sell_price=price * ratio,
        )
        return optima_census(problem).slot_actions

    # Net-metered: solar cannot change the plan (the separability result).
    assert plan(heavy_solar, 1.0) == plan(np.zeros(12), 1.0)
    # Export at a quarter of retail: it can, and does.
    assert plan(heavy_solar, 0.25) != plan(np.zeros(12), 0.25)


def test_a_worse_export_credit_makes_the_battery_MORE_valuable():
    """Direction check, because the docs first asserted the opposite.

    The intuition that a poor export credit must hurt the battery ("a discharge
    earns less") only covers discharges that would have been exported. It misses
    the larger effect: a poor credit creates **self-consumption** value. A surplus
    kWh that would have been dumped at ``sell`` can instead be stored and used to
    avoid buying at ``buy``, and that gain grows as ``sell`` falls.

    Solar savings move the other way — the export leg is worth less — so the two
    legs must be read separately, which is exactly what the three-way split is for.
    """
    price = np.full(24, 0.30)
    price[17:21] = 0.60
    load = np.ones(24) * 1.5
    generation = np.zeros(24)
    generation[8:16] = 4.0          # a normal solar day: midday surplus

    def legs(ratio):
        problem = BatteryProblem(
            generation=generation, load=load, price=price, capacity=10.0,
            charge_energy=2.0, discharge_energy=2.0, initial_soc=4.0,
            sell_price=price * ratio,
        )
        zero = np.zeros(problem.num_slots, dtype=np.int8)
        no_system = float(problem.slot_cost(problem.load).sum())
        solar_only = problem.grid_cost(zero, zero)
        return no_system - solar_only, solar_only - dp_solve(problem).true_energy

    battery = [legs(r)[1] for r in (1.0, 0.75, 0.5, 0.25)]
    solar = [legs(r)[0] for r in (1.0, 0.75, 0.5, 0.25)]
    assert all(a <= b + 1e-9 for a, b in zip(battery, battery[1:])), battery
    assert all(a >= b - 1e-9 for a, b in zip(solar, solar[1:])), solar
    assert battery[-1] > battery[0]     # strictly better, not merely non-worse


def test_charging_from_surplus_solar_becomes_worthwhile():
    """A battery earns a second way once export pays badly: self-consumption.

    Exporting a surplus kWh earns `sell`; storing it and using it later avoids
    buying at `buy`. Under net metering those are equal and there is nothing to
    gain, which is why the net-metered plan ignores solar entirely.
    """
    price = np.full(8, 0.40)
    load = np.ones(8)
    generation = np.zeros(8)
    generation[1:4] = 5.0           # surplus early, none later

    def saving(ratio):
        problem = BatteryProblem(
            generation=generation, load=load, price=price, capacity=4.0,
            charge_energy=1.0, discharge_energy=1.0, initial_soc=2.0,
            sell_price=price * ratio,
        )
        idle = problem.energy(np.zeros(2 * problem.num_slots, dtype=np.int8))
        return idle - dp_solve(problem).true_energy

    # Flat price: net metering leaves nothing to arbitrage, so the battery is idle.
    assert saving(1.0) == pytest.approx(0.0)
    # A poor export credit gives the same flat-price day a real saving.
    assert saving(0.25) > 0.0
