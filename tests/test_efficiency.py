"""Round-trip losses: the model with ``charge/discharge_efficiency < 1``.

The design claim under test is that losses belong in the **price**, not in the
state of charge. The two energy quanta stay store-side and equal, so SoC remains
on the uniform grid the DP and the slack encoding both need; the efficiencies
convert to grid-side energy inside the objective only.

That claim is only worth anything if every solver agrees under it, so the
cross-checks the repo already runs losslessly (DP vs brute force vs the QUBO
surrogate) are re-run here with losses on. Without these, the lossy path would be
exercised by nothing.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantum_solar import (
    BatteryProblem,
    brute_force_solve,
    build_qubo,
    default_weights,
    dp_solve,
    synthetic_instance,
)
from quantum_solar.dynamic_programming import optima_census
from quantum_solar.qubo_search import qubo_min_exact

ETAS = [1.0, 0.95, 0.9487, 0.9, 0.8]


def lossy(problem: BatteryProblem, charge_eff: float, discharge_eff: float | None = None):
    """Same instance with efficiencies applied (store-side quanta untouched)."""
    discharge_eff = charge_eff if discharge_eff is None else discharge_eff
    return BatteryProblem(
        generation=problem.generation, load=problem.load, price=problem.price,
        capacity=problem.capacity, charge_energy=problem.charge_energy,
        discharge_energy=problem.discharge_energy, initial_soc=problem.initial_soc,
        charge_efficiency=charge_eff, discharge_efficiency=discharge_eff,
    )


def test_defaults_are_lossless():
    problem = synthetic_instance(4, seed=0)
    assert problem.charge_efficiency == 1.0
    assert problem.round_trip_efficiency == 1.0
    assert problem.grid_charge_energy == problem.charge_energy
    assert problem.grid_discharge_energy == problem.discharge_energy


@pytest.mark.parametrize("eta", ETAS)
def test_grid_quanta_bracket_the_store_quanta(eta):
    """Charging imports more than it stores; discharging delivers less than it removes."""
    problem = lossy(synthetic_instance(4, seed=0), eta)
    assert problem.grid_charge_energy >= problem.charge_energy
    assert problem.grid_discharge_energy <= problem.discharge_energy
    assert problem.round_trip_efficiency == pytest.approx(eta * eta)
    # A full cycle delivers round_trip * imported.
    delivered = problem.grid_discharge_energy
    imported = problem.grid_charge_energy
    assert delivered / imported == pytest.approx(problem.round_trip_efficiency)


@pytest.mark.parametrize("eta", ETAS)
def test_soc_grid_is_untouched_by_losses(eta):
    """Losses must not move the SoC grid -- that is the whole point of the design."""
    base = synthetic_instance(5, seed=1, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    problem = lossy(base, eta)
    solution = dp_solve(problem)
    charge, discharge = problem.decode(solution.x)
    soc = problem.soc_trajectory(charge, discharge)
    assert np.allclose(soc, np.round(soc / problem.charge_energy) * problem.charge_energy)
    assert soc.min() >= -1e-9 and soc.max() <= problem.capacity + 1e-9
    assert solution.feasible


@pytest.mark.parametrize("eta", ETAS)
@pytest.mark.parametrize("seed", [0, 2, 5])
def test_dp_matches_brute_force_with_losses(eta, seed):
    """The DP and an exhaustive QUBO enumeration must still agree once losses are on.

    This is the load-bearing check: it exercises `grid_cost`, the DP recurrence and
    `build_qubo`'s objective at once, so a coefficient applied in one place and not
    another shows up here.
    """
    base = synthetic_instance(4, seed=seed, capacity=3.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=1.0)
    problem = lossy(base, eta)
    qubo = build_qubo(problem, default_weights(problem))
    brute = brute_force_solve(problem, qubo)
    dp = dp_solve(problem)
    assert brute.feasible and dp.feasible
    assert dp.true_energy == pytest.approx(brute.true_energy)


@pytest.mark.parametrize("eta", ETAS)
def test_qubo_search_matches_dp_with_losses(eta):
    """The scalable surrogate search agrees with the DP optimum under losses."""
    base = synthetic_instance(5, seed=3, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    problem = lossy(base, eta)
    got = qubo_min_exact(problem, default_weights(problem))
    assert got.feasible
    assert got.true_energy == pytest.approx(dp_solve(problem).true_energy)


@pytest.mark.parametrize("eta", [0.95, 0.9, 0.8])
def test_where_the_loss_sits_matters_not_just_the_round_trip(eta):
    """Same round-trip, different split, different bill — so keep two efficiencies.

    Arbitrage buys cheap and sells dear, so the two legs are priced *differently*.
    Energy lost on the charge leg is wasted at the off-peak price; energy lost on
    the discharge leg is wasted at the peak price. Losing it on the cheap leg is
    therefore strictly better, and a single round-trip number cannot express that.

    Break-even is the exception and does depend only on the product: a cycle pays
    iff ``p_hi * eta_d > p_lo / eta_c``, i.e. ``p_hi/p_lo > 1/(eta_c*eta_d)`` —
    which is why :attr:`breakeven_price_ratio` is a function of the round trip
    alone. See ``test_arbitrage_stops_below_the_breakeven_ratio``.
    """
    base = synthetic_instance(5, seed=4, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    root = np.sqrt(eta)
    charge_only = dp_solve(lossy(base, eta, 1.0)).true_energy      # loss when buying
    symmetric = dp_solve(lossy(base, root, root)).true_energy
    discharge_only = dp_solve(lossy(base, 1.0, eta)).true_energy   # loss when selling

    # All three share a round trip of `eta`, yet the bills differ and order strictly.
    for problem in (lossy(base, eta, 1.0), lossy(base, root, root), lossy(base, 1.0, eta)):
        assert problem.round_trip_efficiency == pytest.approx(eta)
        assert problem.breakeven_price_ratio == pytest.approx(1 / eta)
    assert charge_only < symmetric < discharge_only


def test_losses_reduce_the_saving_monotonically():
    """Lower round-trip efficiency can never make the battery earn more."""
    base = synthetic_instance(6, seed=7, capacity=4.0, charge_energy=1.0,
                              discharge_energy=1.0, initial_soc=2.0)
    idle_x = np.zeros(2 * base.num_slots, dtype=np.int8)
    savings = []
    for eta in (1.0, 0.95, 0.9, 0.8, 0.6):
        problem = lossy(base, eta)
        savings.append(problem.energy(idle_x) - dp_solve(problem).true_energy)
    assert all(a >= b - 1e-12 for a, b in zip(savings, savings[1:]))
    assert all(s >= -1e-12 for s in savings)          # never worse than idling


def test_arbitrage_stops_below_the_breakeven_ratio():
    """Below `1 / round_trip`, a cycle loses money and the optimum is to do nothing.

    The lossless model has no such threshold: any spread at all pays. This is the
    qualitative behavior losslessness was hiding.
    """
    # Price ratio 3/2 = 1.5, so arbitrage pays iff round_trip > 1/1.5 = 0.667.
    price = np.array([0.20, 0.20, 0.30, 0.30, 0.20, 0.20])
    base = BatteryProblem(
        generation=np.zeros(6), load=np.ones(6), price=price,
        capacity=4.0, charge_energy=1.0, discharge_energy=1.0, initial_soc=2.0,
    )
    profitable = lossy(base, np.sqrt(0.80))          # round-trip 0.80 > 0.667
    marginal = lossy(base, np.sqrt(0.60))            # round-trip 0.60 < 0.667
    assert marginal.breakeven_price_ratio == pytest.approx(1 / 0.60)

    idle_x = np.zeros(12, dtype=np.int8)
    assert profitable.energy(idle_x) - dp_solve(profitable).true_energy > 0
    # Below break-even the battery cannot beat idling, so it stays put.
    below = dp_solve(marginal)
    charge, discharge = marginal.decode(below.x)
    assert charge.sum() == 0 and discharge.sum() == 0
    assert below.true_energy == pytest.approx(marginal.energy(idle_x))


def test_annual_loop_actually_applies_the_efficiencies():
    """Regression: the annual loop accepted the kwargs and silently dropped them.

    ``annual_from_inputs`` threaded ``charge_efficiency`` into its own signature but
    not into the per-day ``build_instance`` call, so every round trip returned the
    identical lossless total. Nothing failed — it just answered the wrong question
    with a plausible number, which is the failure mode this repo keeps meeting
    (``docs/LESSONS.md`` §7). Assert the output *responds* to the input.
    """
    from quantum_solar.annual import annual_from_inputs

    rng = np.random.default_rng(0)
    generation = np.abs(rng.normal(1.0, 0.5, 8760))
    price_peak = np.full(24, 0.14)
    price_peak[17:21] = 0.38

    def price_for(month, weekend):
        return np.full(24, 0.14) if weekend else price_peak

    def load_for(month, day_type):
        return np.full(24, 1.0)

    totals = [
        annual_from_inputs(
            generation, price_for, load_for, days=range(20),
            capacity=10.0, charge_energy=2.0, discharge_energy=2.0,
            charge_efficiency=eff, discharge_efficiency=eff,
        ).battery_savings
        for eff in (1.0, np.sqrt(0.9), np.sqrt(0.8))
    ]
    assert totals[0] > totals[1] > totals[2] > 0
    assert len(set(round(t, 6) for t in totals)) == 3   # all distinct, not passed through


@pytest.mark.parametrize("eta", [1.0, 0.9487, 0.8944])
def test_losses_do_not_couple_the_plan_to_solar_or_load(eta):
    """Losses rescale the battery term; they do not re-couple it to the household.

    `ARCHITECTURE.md` claimed for a while that round-trip losses would break the
    net-metering separability. They do not, and this pins the correction: the bill
    is still `price @ (load - generation)` plus a battery term that mentions
    neither, so only the coefficients move. Only an asymmetric buy/sell price can
    couple them, by making *which* price applies depend on the household's net.
    """
    price = np.full(12, 0.14)
    price[7:10] = 0.38
    rng = np.random.default_rng(0)

    def plan(generation, load):
        """The tie-break-independent plan: which actions are optimal in each slot.

        NOT the schedule ``dp_solve`` happens to return. The optimum is massively
        degenerate (every equal-priced hour is interchangeable), so the returned
        schedule shifts under float-level changes while the *set* of optimal
        actions does not. Comparing the raw schedule is the mistake this repo
        documents under ``optima_census``.
        """
        problem = BatteryProblem(
            generation=generation, load=load, price=price, capacity=4.0,
            charge_energy=1.0, discharge_energy=1.0, initial_soc=2.0,
            charge_efficiency=eta, discharge_efficiency=eta,
        )
        return optima_census(problem).slot_actions

    reference = plan(np.zeros(12), np.ones(12))
    assert plan(np.full(12, 3.0), np.ones(12)) == reference           # lots of solar
    assert plan(np.zeros(12), np.full(12, 9.0)) == reference          # heavy load
    assert plan(rng.uniform(0, 3, 12), rng.uniform(0, 3, 12)) == reference


def test_losses_collapse_the_cost_free_degeneracy():
    """The huge tie counts were an artifact of losslessness, not a real feature.

    Losslessly, a charge and a discharge at one price cancel exactly, so a flat day
    has every feasible schedule tied for optimal. With losses that pair strictly
    loses money, so the optimum becomes unique: do nothing.
    """
    flat = BatteryProblem(
        generation=np.zeros(8), load=np.ones(8), price=np.full(8, 0.14),
        capacity=4.0, charge_energy=1.0, discharge_energy=1.0, initial_soc=2.0,
    )
    assert optima_census(flat).n_optima > 1            # lossless: everything ties
    lossy_census = optima_census(lossy(flat, 0.95))
    assert lossy_census.n_optima == 1
    assert lossy_census.min_actions == 0
