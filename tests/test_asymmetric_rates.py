"""Asymmetric charge/discharge energy per slot — the last v1 assumption.

Real inverters routinely charge and discharge at different rates, and the spec
sheet quotes both. The constraint that blocked this was structural rather than
economic: the state of charge has to live on a uniform grid for the DP to be a
path problem and for the slack encoding to be representable.

It still does. Reachable states are ``S_0 + n_c*e_c - n_d*e_d``, which lie on a
uniform grid **iff the two quanta are commensurate**, and then the step is their
GCD. So asymmetric rates *refine* the grid rather than destroying it — at a real
cost in qubits, which is measured below.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantum_solar import (
    BatteryProblem,
    Encoding,
    brute_force_solve,
    build_qubo,
    default_weights,
    dp_solve,
    num_vars,
)
from quantum_solar.dynamic_programming import optima_census
from quantum_solar.problem import MAX_SOC_LEVELS, soc_quantum
from quantum_solar.qubo_search import qubo_min_exact

# (charge_energy, discharge_energy) pairs that share a workable grid.
PAIRS = [(1.0, 1.0), (2.0, 1.0), (1.0, 2.0), (2.0, 1.5), (0.5, 1.0), (1.5, 0.5)]


def instance(charge, discharge, *, capacity=4.0, initial_soc=2.0, slots=3):
    price = np.full(slots, 0.1)
    price[slots // 2] = 0.9
    return BatteryProblem(
        generation=np.zeros(slots), load=np.ones(slots), price=price,
        capacity=capacity, charge_energy=charge, discharge_energy=discharge,
        initial_soc=initial_soc,
    )


@pytest.mark.parametrize("charge,discharge,expected", [
    (2.0, 2.0, 2.0), (1.0, 1.0, 1.0),        # symmetric: the quantum is the rate
    (2.0, 1.0, 1.0), (1.0, 2.0, 1.0),        # one divides the other
    (2.0, 1.5, 0.5), (1.5, 2.5, 0.5), (0.5, 0.75, 0.25),
])
def test_soc_quantum_is_the_gcd(charge, discharge, expected):
    assert soc_quantum(instance(charge, discharge)) == pytest.approx(expected)


def test_symmetric_rates_are_unchanged():
    """The v1 case must be bit-identical: the quantum is just the shared rate."""
    problem = instance(2.0, 2.0, capacity=10.0, initial_soc=4.0)
    assert soc_quantum(problem) == problem.charge_energy


@pytest.mark.parametrize("charge,discharge", PAIRS)
def test_dp_matches_brute_force_and_qubo_search(charge, discharge):
    """All three exact solvers agree once the grid is refined, not just the DP.

    This is the check that the change is real rather than only self-consistent:
    ``build_qubo``'s penalties, the exhaustive enumeration, and the surrogate search
    each derive the SoC path independently.
    """
    problem = instance(charge, discharge)
    weights = default_weights(problem)
    qubo = build_qubo(problem, weights)
    assert qubo.num_vars <= 20, "instance outgrew brute force; shrink it"
    dp = dp_solve(problem)
    brute = brute_force_solve(problem, qubo)
    search = qubo_min_exact(problem, weights)
    assert dp.feasible and brute.feasible and search.feasible
    assert dp.true_energy == pytest.approx(brute.true_energy)
    assert dp.true_energy == pytest.approx(search.true_energy)


@pytest.mark.parametrize("charge,discharge", PAIRS)
def test_schedule_stays_on_grid_and_in_bounds(charge, discharge):
    problem = instance(charge, discharge)
    solution = dp_solve(problem)
    c, d = problem.decode(solution.x)
    soc = problem.soc_trajectory(c, d)
    quantum = soc_quantum(problem)
    assert np.allclose(soc / quantum, np.round(soc / quantum))
    assert soc.min() >= -1e-9 and soc.max() <= problem.capacity + 1e-9
    assert soc[-1] == pytest.approx(problem.initial_soc)   # returns to start
    assert solution.feasible


def test_asymmetric_round_trip_uses_unequal_action_counts():
    """The behaviour the constraint forbade: 2 kWh in balanced by 2 x 1 kWh out.

    Under ``e_c == e_d`` every optimal schedule has equal charge and discharge
    counts, because each action moves one grid level. Asymmetric rates break that,
    and the terminal constraint is satisfied by *energy*, not by action count.
    """
    problem = BatteryProblem(
        generation=np.zeros(5), load=np.ones(5),
        price=np.array([0.1, 0.9, 0.9, 0.1, 0.1]),
        capacity=4.0, charge_energy=2.0, discharge_energy=1.0, initial_soc=2.0,
    )
    c, d = problem.decode(dp_solve(problem).x)
    assert d.sum() == 2 and c.sum() == 1          # two small out, one big in
    assert problem.soc_trajectory(c, d)[-1] == pytest.approx(2.0)


def test_incommensurate_rates_are_rejected():
    """No finite grid holds both, so fail loudly instead of building 9M levels."""
    problem = instance(2.0, 2.0 * np.sqrt(2.0), capacity=10.0, initial_soc=0.0)
    with pytest.raises(ValueError, match=f"over the {MAX_SOC_LEVELS} cap"):
        dp_solve(problem)


def test_grid_checks_use_the_gcd():
    """``require_soc_on_grid`` measures against the refined quantum, not either rate.

    4.25 is off the 0.5 grid that 2.0-in/1.5-out implies, so it is rejected — the
    same guard that catches an off-grid capacity in the symmetric case, now applied
    to the finer grid asymmetry produces.
    """
    problem = instance(2.0, 1.5, capacity=4.25, initial_soc=2.0)
    assert soc_quantum(problem) == pytest.approx(0.5)
    with pytest.raises(ValueError, match="capacity=4.25 is not a multiple"):
        dp_solve(problem)


def test_asymmetry_costs_qubits():
    """A finer grid needs a wider slack register — the encoding-cost tradeoff.

    Worth stating plainly because it is the project's recurring theme: the exact
    SoC encoding buys correctness with qubits, and asymmetric rates raise the
    price. A 2.0/1.5 split quarters the quantum relative to 2.0 and widens every
    interior slot's slack block.
    """
    symmetric = instance(2.0, 2.0, capacity=8.0, initial_soc=4.0, slots=4)
    asymmetric = instance(2.0, 1.5, capacity=8.0, initial_soc=4.0, slots=4)
    assert soc_quantum(symmetric) == 2.0
    assert soc_quantum(asymmetric) == 0.5
    assert num_vars(asymmetric) > num_vars(symmetric)


def test_drift_encoding_rejects_asymmetric_rates_in_the_search():
    """WindowDrift packs each step into a base-3 digit, which asymmetry overflows.

    Every other encoding has no drift term and is unaffected; this raises rather
    than returning a quietly wrong optimum.
    """
    problem = instance(2.0, 1.0, capacity=4.0, initial_soc=2.0, slots=4)
    encoding = Encoding.window_drift(3)
    with pytest.raises(ValueError, match="drift-window encoding with asymmetric"):
        qubo_min_exact(problem, default_weights(problem), encoding)


def test_census_handles_asymmetric_steps():
    """The forward/backward census must walk the same uneven steps as the DP."""
    problem = instance(2.0, 1.0, capacity=4.0, initial_soc=2.0, slots=4)
    census = optima_census(problem)
    charge, discharge = problem.decode(dp_solve(problem).x)
    assert len(census.slot_actions) == problem.num_slots
    assert census.n_minimal >= 1
    # dp_solve returns *an* optimum, so it can use no fewer actions than the
    # minimum the census found, and no more than the schedule it actually returned.
    assert census.min_actions <= int(charge.sum() + discharge.sum())
    assert all(a for a in census.slot_actions)   # every slot has some optimal action


# --- the buyer-facing consequence -------------------------------------------

PEAK_HOURS, SPREAD, OFF_PEAK = 4, 0.24183, 0.13926


def sizing_saving(capacity, charge, discharge):
    price = np.full(24, OFF_PEAK)
    price[21 - PEAK_HOURS:21] = OFF_PEAK + SPREAD
    probe = BatteryProblem(
        generation=np.zeros(24), load=np.ones(24), price=price, capacity=capacity,
        charge_energy=charge, discharge_energy=discharge, initial_soc=0.0,
    )
    quantum = soc_quantum(probe)
    problem = BatteryProblem(
        generation=np.zeros(24), load=np.ones(24), price=price, capacity=capacity,
        charge_energy=charge, discharge_energy=discharge,
        initial_soc=round((capacity / 2) / quantum) * quantum,
    )
    idle = problem.energy(np.zeros(2 * problem.num_slots, dtype=np.int8))
    return idle - dp_solve(problem).true_energy


@pytest.mark.parametrize("charge,discharge", [(2.0, 2.0), (1.0, 2.0), (4.0, 2.0),
                                              (2.0, 1.0), (2.0, 0.5)])
def test_discharge_rate_sets_the_sizing_ceiling(charge, discharge):
    """`min(capacity, DISCHARGE rate x peak_hours) x spread` — charge rate drops out.

    Only discharging inside the peak window earns, so it is the discharge rating
    that caps the saving. The charge rating does not appear at all, provided it can
    refill in the off-peak hours available (see the next test for when it cannot).
    """
    got = sizing_saving(10.0, charge, discharge)
    assert got == pytest.approx(min(10.0, discharge * PEAK_HOURS) * SPREAD, abs=5e-4)


def test_a_too_slow_charge_rate_becomes_the_binding_constraint():
    """The exception: charging so slowly that the battery cannot be refilled."""
    fast = sizing_saving(10.0, 2.0, 2.0)
    slow = sizing_saving(10.0, 0.5, 2.0)
    assert slow < fast
    assert slow < min(10.0, 2.0 * PEAK_HOURS) * SPREAD - 5e-4
