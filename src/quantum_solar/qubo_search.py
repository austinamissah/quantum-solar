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
   is a reachable assignment; it carries the mutual-exclusion penalty and moves SoC
   by ``e_c − e_d``, which is zero only when the rates are symmetric. Including it
   is what makes this minimize over all ``2^{2T}`` rather than over ``3^T``
   schedules.
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

from .encodings import Encoding, SoCEncoding, soc_grid, soc_steps
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

    t = problem.num_slots
    e, _, k0 = soc_grid(problem)
    up, down = soc_steps(problem)
    # Per-action SoC step in grid levels. Charging and discharging need not be
    # symmetric, and `c == d == 1` no longer cancels when they are not.
    actions = ((0, 0, 0), (1, 0, up), (0, 1, -down), (1, 1, up - down))
    idle_cost, charge_delta, discharge_delta, both = problem.action_costs()

    # --- State space: every reachable SoC level, plus drift history if needed ---
    # T slots can climb T*up or fall T*down levels from the start.
    levels = np.arange(k0 - t * down, k0 + t * up + 1)
    n_lev = len(levels)
    start_index = t * down          # index of k0 in `levels`
    drift = encoding.drift_spec(problem, weights.soc_bounds)
    window, drift_coef = drift if drift else (0, 0.0)
    hist_len = max(0, window - 1)
    if hist_len and (up != 1 or down != 1):
        # The history packs each step into one base-3 digit (-1/0/+1), which cannot
        # represent the four distinct steps asymmetric rates produce. Only
        # WindowDrift takes this path; every other encoding has no drift term.
        raise ValueError(
            "qubo_min_exact cannot combine a drift-window encoding with asymmetric "
            f"charge/discharge energy (charge_energy={problem.charge_energy}, "
            f"discharge_energy={problem.discharge_energy}). Use a non-drift encoding "
            "or equal energies."
        )
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
        for a, (_, _, dk) in enumerate(actions):
            trans[h, a] = ((h % 3 ** max(0, hist_len - 1)) * 3 + dk + 1) if hist_len else 0

    # --- Level-dependent costs paid on arriving after each slot ---
    slot_pen = encoding.slot_penalty(problem, weights.soc_bounds, levels)
    terminal_pen = weights.terminal * (e * (levels - k0)) ** 2
    arrive = [slot_pen[j] if j < t - 1 else terminal_pen for j in range(t)]

    cost = np.full((n_lev, n_hist), np.inf)
    cost[start_index, 0] = 0.0  # start at k_0; empty history
    bp_action = np.zeros((t, n_lev, n_hist), dtype=np.int8)
    bp_hist = np.zeros((t, n_lev, n_hist), dtype=np.int16)

    for j in range(t):
        p = problem.price[j]
        nxt = np.full((n_lev, n_hist), np.inf)
        for a, (c, d, dk) in enumerate(actions):
            src = slice(max(0, -dk), n_lev - max(0, dk))
            tgt = slice(max(0, dk), n_lev + min(0, dk))
            # Per-slot action cost (round-trip losses and, when export credits
            # below import, a piecewise bill); the SoC steps `dk` stay store-side.
            step = float(charge_delta[j] * c + discharge_delta[j] * d
                         + (both[j] if c and d else 0.0)
                         + (weights.mutual_exclusion if c and d else 0.0))
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
    qubo_energy = float(cost[i, h] + idle_cost.sum())

    # --- Walk back for the schedule and its SoC path ---
    c = np.zeros(t, dtype=np.int8)
    d = np.zeros(t, dtype=np.int8)
    path = np.zeros(t, dtype=int)
    for j in range(t - 1, -1, -1):
        a = int(bp_action[j, i, h])
        c[j], d[j], dk = actions[a]
        path[j] = levels[i]          # SoC level after slot j
        h = int(bp_hist[j, i, h])    # predecessor history, before stepping the level
        i -= dk
    assert i == start_index, "backtrack did not return to the initial SoC index"
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
