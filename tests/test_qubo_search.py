"""``qubo_min_exact`` must agree with brute force wherever brute force can reach.

The DP in :mod:`quantum_solar.qubo_search` re-expresses every encoding's penalty
as a function of the SoC path, so it is a *second* implementation of the same
math as ``build_qubo``. These tests are the only thing stopping the two from
drifting apart, so they enumerate every encoding at every size brute force can
still enumerate — including the 4-action ``c_t = d_t = 1`` states and the
auxiliary reconstruction, both of which are easy to get subtly wrong.
"""

from __future__ import annotations

import numpy as np
import pytest

from quantum_solar import (
    Encoding,
    PenaltyWeights,
    brute_force_solve,
    build_qubo,
    default_weights,
    dp_solve,
    max_sound_spacing,
    synthetic_instance,
)
from quantum_solar.brute_force import enumerate_bitstrings
from quantum_solar.qubo_search import qubo_min_exact


def qubo_energy_diagonal(qubo):
    """Energy of every basis assignment, indexed by basis integer."""
    x = enumerate_bitstrings(qubo.num_vars).astype(float)
    return np.einsum("bi,ij,bj->b", x, qubo.Q, x) + qubo.offset

# Instances small enough to brute-force, spanning capacity and initial SoC.
INSTANCES = [
    pytest.param(3.0, 1.0, id="Q3-S1"),
    pytest.param(3.0, 2.0, id="Q3-S2"),
    pytest.param(4.0, 2.0, id="Q4-S2"),
]


def _problem(t, capacity, initial_soc, seed=0):
    return synthetic_instance(
        t,
        seed=seed,
        capacity=capacity,
        charge_energy=1.0,
        discharge_energy=1.0,
        initial_soc=initial_soc,
    )


def _encodings(problem):
    k = max_sound_spacing(problem)
    encs = [
        ("exact", Encoding.EXACT),
        ("none", Encoding.NONE),
        ("center", Encoding.center_anchor()),
        ("center-0.1", Encoding.center_anchor(weight_scale=0.1)),
    ]
    for spacing in range(1, k + 1):
        encs.append((f"cp{spacing}", Encoding.checkpoint(spacing)))
        encs.append((f"cp{spacing}-banded", Encoding.checkpoint(spacing, banded=True)))
    for w in (1, 2, 3):
        if w <= problem.num_slots:
            encs.append((f"wd{w}", Encoding.window_drift(w)))
            encs.append((f"wd{w}-0.1", Encoding.window_drift(w, weight_scale=0.1)))
    return encs


@pytest.mark.parametrize("capacity,initial_soc", INSTANCES)
@pytest.mark.parametrize("t", [2, 3, 4])
def test_matches_brute_force(t, capacity, initial_soc):
    """The DP finds the same QUBO minimum as exhaustive enumeration."""
    problem = _problem(t, capacity, initial_soc)
    weights = default_weights(problem)
    for name, encoding in _encodings(problem):
        qubo = build_qubo(problem, weights, encoding)
        if qubo.num_vars > 16:
            continue
        bf = brute_force_solve(problem, qubo)
        dp = qubo_min_exact(problem, weights, encoding)
        assert dp.qubo_energy == pytest.approx(bf.qubo_energy, abs=1e-9), name


@pytest.mark.parametrize("capacity,initial_soc", INSTANCES)
@pytest.mark.parametrize("t", [2, 3, 4])
def test_returned_vector_is_a_valid_minimizer(t, capacity, initial_soc):
    """``x`` is a full QUBO vector whose energy equals the reported minimum.

    This is what catches a wrong ``aux_assignment``: the DP can find the right
    *value* by minimizing slack out analytically while rebuilding slack bits that
    do not achieve it.
    """
    problem = _problem(t, capacity, initial_soc)
    weights = default_weights(problem)
    for name, encoding in _encodings(problem):
        qubo = build_qubo(problem, weights, encoding)
        dp = qubo_min_exact(problem, weights, encoding)
        assert dp.x.shape == (qubo.num_vars,), name
        assert qubo.energy(dp.x) == pytest.approx(dp.qubo_energy, abs=1e-9), name
        assert problem.energy(dp.x) == pytest.approx(dp.true_energy, abs=1e-9), name
        assert problem.is_feasible(dp.x) == dp.feasible, name


def test_counts_mutual_exclusion_states():
    """The 4th action is reachable: dropping it would miss part of the QUBO.

    With the mutual-exclusion penalty set to zero, ``c_t = d_t = 1`` costs exactly
    what idling costs, so the minimum must not change — a 3-action DP over
    schedules would agree here, but the *enumeration* it has to match does not.
    """
    problem = _problem(3, 3.0, 1.0)
    base = default_weights(problem)
    free = type(base)(mutual_exclusion=0.0, soc_bounds=base.soc_bounds, terminal=base.terminal)
    for encoding in (Encoding.EXACT, Encoding.checkpoint(3), Encoding.NONE):
        qubo = build_qubo(problem, free, encoding)
        bf = brute_force_solve(problem, qubo)
        dp = qubo_min_exact(problem, free, encoding)
        assert dp.qubo_energy == pytest.approx(bf.qubo_energy, abs=1e-9)


def test_exact_encoding_recovers_the_true_optimum():
    """``Encoding.EXACT`` is exact: its QUBO optimum is the true optimum."""
    for t in (2, 3, 4, 6, 12):
        problem = _problem(t, 3.0, 1.0)
        weights = default_weights(problem)
        dp = qubo_min_exact(problem, weights, Encoding.EXACT)
        truth = dp_solve(problem)
        assert dp.feasible
        assert dp.true_energy == pytest.approx(truth.true_energy, abs=1e-9), t


def test_checkpoint_is_sound_at_scale():
    """Checkpoint never returns an infeasible schedule, well past brute-force range."""
    for t in (6, 12, 24):
        problem = _problem(t, 3.0, 1.0)
        weights = default_weights(problem)
        for spacing in range(1, max_sound_spacing(problem) + 1):
            dp = qubo_min_exact(problem, weights, Encoding.checkpoint(spacing))
            assert dp.feasible, (t, spacing)
            assert dp.true_energy >= dp_solve(problem).true_energy - 1e-9


def test_scales_past_brute_force():
    """A full day is solvable for every encoding — the point of the module."""
    problem = _problem(24, 3.0, 1.0)
    weights = default_weights(problem)
    for name, encoding in _encodings(problem):
        dp = qubo_min_exact(problem, weights, encoding)
        assert np.isfinite(dp.qubo_energy), name


def test_every_zero_penalty_assignment_is_feasible():
    """Soundness in the strong form the write-ups state, checked exhaustively.

    ``test_checkpoint_is_sound_at_scale`` covers the *minimum-energy* assignment at
    sizes brute force cannot reach. This covers the stronger sentence the write-ups
    actually publish -- "every zero-penalty assignment is genuinely feasible" -- by
    enumerating the whole register at sizes where that is possible.

    That sentence is the one load-bearing claim in `docs/FINDINGS.md`: removing slack
    variables is a crowded field, and what distinguishes `Checkpoint` from the
    published alternatives is that it is a guarantee rather than a bias. A guarantee
    asserted only about the minimum is a weaker claim than the one being made, so it
    is checked here about every assignment.

    Penalty is isolated by differencing against a zero-weight QUBO on the same
    encoding, so this tests `build_qubo`'s penalty terms directly rather than any
    reimplementation of them.
    """
    free = PenaltyWeights(mutual_exclusion=0.0, soc_bounds=0.0, terminal=0.0)

    for t, capacity, initial in ((3, 3.0, 1.0), (4, 3.0, 1.0), (4, 4.0, 2.0)):
        problem = _problem(t, capacity, initial)
        weights = default_weights(problem)
        for spacing in range(1, max_sound_spacing(problem) + 1):
            for banded in (False, True):
                encoding = Encoding.checkpoint(spacing, banded=banded)
                penalised = build_qubo(problem, weights, encoding)
                objective = build_qubo(problem, free, encoding)
                assert penalised.num_vars == objective.num_vars

                states = enumerate_bitstrings(penalised.num_vars)
                penalty = (qubo_energy_diagonal(penalised)
                           - qubo_energy_diagonal(objective))
                zero = np.flatnonzero(penalty <= 1e-9)
                assert zero.size, (t, spacing, banded, "no zero-penalty assignment")

                for index in zero:
                    assert problem.is_feasible(states[index]), (
                        f"T={t} cap={capacity} spacing={spacing} banded={banded}: "
                        f"assignment {index} carries zero penalty but is infeasible, "
                        f"so the encoding is NOT sound"
                    )


def test_the_soundness_guard_refuses_an_unsound_spacing():
    """Guard the guard: past `max_sound_spacing` the encoding must refuse, not bias.

    If it silently accepted, the test above would pass vacuously on a spacing that
    has no guarantee, which is exactly the failure `docs/FINDINGS.md` says the
    published alternatives have.
    """
    problem = _problem(6, 3.0, 1.0)
    too_far = max_sound_spacing(problem) + 1
    with pytest.raises(ValueError, match="headroom"):
        build_qubo(problem, default_weights(problem), Encoding.checkpoint(too_far))
