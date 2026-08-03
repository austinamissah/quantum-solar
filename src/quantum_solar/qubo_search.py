"""Exact minimization of the QUBO *surrogate*, at any ``T``.

``dp_solve`` gives the exact optimum of the **true** problem. To ask how often an
approximate encoding's optimum differs from it, we also need the exact optimum of
the **QUBO** — and ``brute_force_solve`` caps that at ``MAX_ENUMERATION_SITES``
(20) variables, i.e. ``T ≤ 5`` exact or ``T ≤ 10`` slack-free. This module lifts
that ceiling.

Every encoding's penalty is a function of the SoC path, so the same ``O(T·K)``
argument that makes ``dp_solve`` work applies here too, with three changes that
turn "solve the problem" into "minimize the surrogate":

1. **Extended grid.** ``dp_solve`` enforces ``0 ≤ S_t ≤ Q`` structurally by
   omitting out-of-range transitions. Here bound violations must be *represented*
   so their penalty can be paid, so the grid runs over every reachable level,
   ``k_0 − T … k_0 + T``.
2. **Four actions, not three.** The QUBO has ``2T`` free bits, so ``c_t = d_t = 1``
   is a reachable assignment; it carries the mutual-exclusion penalty and (in v1,
   where ``e_c == e_d``) leaves SoC unchanged. Including it is what makes this
   minimize over all ``2^{2T}`` rather than over ``3^T`` schedules.
3. **Auxiliary variables minimized out.** Slack bits are unconstrained, so for a
   given path each takes its best value analytically — that is what
   ``SoCEncoding.slot_penalty`` returns. The winning assignment is rebuilt
   afterwards by ``aux_assignment`` so the returned ``x`` is a full QUBO vector.

:class:`WindowDrift` couples slots ``W`` apart, so the state is augmented with the
last ``W−1`` moves (``3^{W−1}`` extra states — 27 at ``W=4``).

This is a second implementation of the same penalties as
:func:`quantum_solar.qubo.build_qubo`, so it can drift from them. The guard is
``tests/test_qubo_search.py``, which asserts equality with ``brute_force_solve``
for every encoding at every size brute force can reach.
"""

from __future__ import annotations

import numpy as np

from .encodings import Encoding, SoCEncoding, soc_grid
from .problem import BatteryProblem, require_soc_on_grid
from .qubo import PenaltyWeights
from .solution import Solution

# Actions on the 2T decision bits: (c, d) -> SoC step in grid units.
_ACTIONS = ((0, 0, 0), (1, 0, 1), (0, 1, -1), (1, 1, 0))


def qubo_min_exact(
    problem: BatteryProblem,
    weights: PenaltyWeights,
    encoding: SoCEncoding = Encoding.EXACT,
) -> Solution:
    """Exactly minimize the QUBO that ``build_qubo`` would produce.

    Returns the minimizer as a full QUBO vector (decision bits followed by the
    encoding's auxiliary block), with ``qubo_energy`` the surrogate's minimum and
    ``true_energy``/``feasible`` measured against the real problem — so comparing
    against ``dp_solve`` directly answers "did the surrogate's optimum survive".
    """
    require_soc_on_grid(problem)
    encoding.validate(problem)
    if not np.isclose(problem.charge_energy, problem.discharge_energy):
        raise ValueError("qubo_min_exact requires charge_energy == discharge_energy (v1)")

    t = problem.num_slots
    e, _, k0 = soc_grid(problem)
    e_c, e_d = problem.charge_energy, problem.discharge_energy

    # --- State space: every reachable SoC level, plus drift history if needed ---
    levels = np.arange(k0 - t, k0 + t + 1)
    n_lev = len(levels)
    drift = encoding.drift_spec(problem, weights.soc_bounds)
    window, drift_coef = drift if drift else (0, 0.0)
    hist_len = max(0, window - 1)
    n_hist = 3**hist_len

    # hist packs the last `hist_len` steps, most recent in the least significant
    # base-3 digit (0/1/2 meaning a step of -1/0/+1).
    digits = np.array(
        [[(h // 3**i) % 3 - 1 for i in range(hist_len)] for h in range(n_hist)],
        dtype=int,
    ).reshape(n_hist, hist_len)
    hist_sum = digits.sum(axis=1) if hist_len else np.zeros(n_hist, dtype=int)
    trans = np.zeros((n_hist, 4), dtype=int)
    for h in range(n_hist):
        for a, (_, _, dk) in enumerate(_ACTIONS):
            trans[h, a] = ((h % 3 ** max(0, hist_len - 1)) * 3 + dk + 1) if hist_len else 0

    # --- Level-dependent costs paid on arriving after each slot ---
    slot_pen = encoding.slot_penalty(problem, weights.soc_bounds, levels)
    terminal_pen = weights.terminal * (e * (levels - k0)) ** 2
    arrive = [slot_pen[j] if j < t - 1 else terminal_pen for j in range(t)]

    cost = np.full((n_lev, n_hist), np.inf)
    cost[t, 0] = 0.0  # start at k_0, index t; empty history
    bp_action = np.zeros((t, n_lev, n_hist), dtype=np.int8)
    bp_hist = np.zeros((t, n_lev, n_hist), dtype=np.int16)

    for j in range(t):
        p = problem.price[j]
        nxt = np.full((n_lev, n_hist), np.inf)
        for a, (c, d, dk) in enumerate(_ACTIONS):
            src = slice(max(0, -dk), n_lev - max(0, dk))
            tgt = slice(max(0, dk), n_lev + min(0, dk))
            step = p * (e_c * c - e_d * d) + (weights.mutual_exclusion if c and d else 0.0)
            for h in range(n_hist):
                total = step
                if window and j >= window - 1:
                    total += drift_coef * (hist_sum[h] + dk) ** 2
                cand = cost[src, h] + total + arrive[j][tgt]
                col = nxt[tgt, trans[h, a]]
                better = cand < col
                col[better] = cand[better]
                bp_action[j][tgt, trans[h, a]][better] = a
                bp_hist[j][tgt, trans[h, a]][better] = h
        cost = nxt

    flat = int(np.argmin(cost))
    i, h = divmod(flat, n_hist)
    qubo_energy = float(cost[i, h] + problem.price @ (problem.load - problem.generation))

    # --- Walk back for the schedule and its SoC path ---
    c = np.zeros(t, dtype=np.int8)
    d = np.zeros(t, dtype=np.int8)
    path = np.zeros(t, dtype=int)
    for j in range(t - 1, -1, -1):
        a = int(bp_action[j, i, h])
        c[j], d[j], dk = _ACTIONS[a]
        path[j] = levels[i]          # SoC level after slot j
        h = int(bp_hist[j, i, h])    # predecessor history, before stepping the level
        i -= dk
    assert i == t, "backtrack did not return to the initial SoC index"
    return _finish(problem, encoding, c, d, path, qubo_energy)


def _finish(
    problem: BatteryProblem,
    encoding: SoCEncoding,
    c: np.ndarray,
    d: np.ndarray,
    path: np.ndarray,
    qubo_energy: float,
) -> Solution:
    x = np.concatenate([c, d, encoding.aux_assignment(problem, path)]).astype(np.int8)
    return Solution(
        x=x,
        qubo_energy=qubo_energy,
        true_energy=problem.energy(x),
        feasible=problem.is_feasible(x),
    )
