"""Exact dynamic-programming solver — the scalable classical baseline.

Because the battery has a fixed energy quantum ``e``, the state of charge lives on
a discrete grid ``{0, e, 2e, …, Q}``. A schedule is a path over that grid, so the
optimum is found by dynamic programming in ``O(T·K·3)`` time (``K`` SoC levels,
three actions per slot) — linear in ``T``, unlike the ``2^{2T}`` brute-force
enumeration of the QUBO.

Crucially, the SoC bounds ``0 ≤ S_t ≤ Q`` are enforced *structurally* here: an
out-of-range transition simply does not exist, so no penalty or slack is needed.
This is the exact optimum of the true problem and the ground truth the QUBO
encoding (and QAOA) are checked against at scale.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .problem import BatteryProblem, require_soc_on_grid
from .solution import Solution

_IDLE, _CHARGE, _DISCHARGE = 0, 1, 2
_ACTION_NAMES = ("idle", "charge", "discharge")


def dp_solve(problem: BatteryProblem) -> Solution:
    """Return the exact cost-minimizing schedule as a :class:`Solution`."""
    e = problem.charge_energy
    if not np.isclose(problem.charge_energy, problem.discharge_energy):
        raise ValueError("DP grid requires charge_energy == discharge_energy (v1)")
    require_soc_on_grid(problem)

    t = problem.num_slots
    n_max = int(round(problem.capacity / e))
    k0 = int(round(problem.initial_soc / e))
    inf = np.inf

    # Forward DP: cost[k] = min cost to reach SoC level k after the processed slots.
    cost = np.full(n_max + 1, inf)
    cost[k0] = 0.0
    actions = np.zeros((t, n_max + 1), dtype=np.int8)  # chosen action to land on k

    for j in range(t):
        p = problem.price[j]
        # The SoC step is store-side (one grid level either way); the PRICE is paid
        # on the grid-side quantum, which is where round-trip losses land.
        idle = cost                                   # k <- k
        charge = np.full(n_max + 1, inf)
        charge[1:] = cost[:-1] + p * problem.grid_charge_energy      # k <- k-1
        discharge = np.full(n_max + 1, inf)
        discharge[:-1] = cost[1:] - p * problem.grid_discharge_energy  # k <- k+1

        stacked = np.vstack([idle, charge, discharge])
        cost = stacked.min(axis=0)
        actions[j] = stacked.argmin(axis=0)

    # Terminal constraint: must end at the initial SoC level.
    total = float(cost[k0] + problem.price @ (problem.load - problem.generation))

    # Reconstruct the schedule backward from k0.
    c = np.zeros(t, dtype=np.int8)
    d = np.zeros(t, dtype=np.int8)
    k = k0
    for j in range(t - 1, -1, -1):
        action = actions[j, k]
        if action == _CHARGE:
            c[j] = 1
            k -= 1
        elif action == _DISCHARGE:
            d[j] = 1
            k += 1
        # _IDLE leaves k unchanged
    assert k == k0

    x = np.concatenate([c, d])
    return Solution(
        x=x,
        qubo_energy=total,   # equals the QUBO energy of the corresponding feasible vector
        true_energy=total,
        feasible=problem.is_feasible(x),
    )


@dataclass(frozen=True)
class OptimaCensus:
    """How many schedules tie for optimal, and which choices are actually forced.

    ``dp_solve`` returns *one* optimal schedule. Under a time-of-use tariff the
    optimum is usually far from unique — every hour at the same price is
    interchangeable — so the specific hours it reports are an artifact of tie-breaking
    and must not be read as "the" answer. This census says how much of the schedule
    is real.

    Attributes:
        n_optima: every cost-optimal schedule. Read this with care **when the
            battery is lossless**: a charge and a discharge at the same price then
            cancel exactly, so the count includes unlimited cost-free cycling that
            a real battery would pay for in wear, and on a flat-price day it counts
            every feasible schedule and carries no information at all. Set a
            round-trip efficiency below 1 and that degeneracy disappears — the
            cancelling pair now strictly loses money — so this count becomes
            meaningful and usually small. The 1.5e10-tie flat day is an artifact of
            the lossless default, not a property of batteries.
        n_minimal: cost-optimal schedules that also use the fewest battery actions.
            This is the meaningful count — it excludes the cost-free churn above.
        min_actions: battery actions (charges + discharges) in those schedules.
        slot_actions: per slot, the action names that occur in *some* minimal
            optimum. A slot with one entry is **forced**; more than one means the
            choice is free and any of them is equally optimal.
    """

    n_optima: int
    n_minimal: int
    min_actions: int
    slot_actions: tuple[tuple[str, ...], ...]

    def forced(self) -> dict[int, str]:
        """``{slot: action}`` for slots where every minimal optimum agrees."""
        return {j: a[0] for j, a in enumerate(self.slot_actions) if len(a) == 1}


def optima_census(problem: BatteryProblem, *, atol: float = 1e-9) -> OptimaCensus:
    """Count tied-optimal schedules and locate the genuinely forced decisions.

    Same ``O(T·K·3)`` recurrence as :func:`dp_solve`, run forward and backward so
    that a slot/action can be tested for membership in some optimum in constant
    time. Counts are exact Python ints (they overflow float64 readily — a flat
    24-hour day has ~1.5e10 tied schedules).

    ``atol`` is the tolerance for calling two costs equal. It is a **classifier**:
    too tight and genuine ties split into spurious distinct optima; too loose and
    near-optimal schedules are absorbed. 1e-9 sits far above float64 accumulation
    error over a day (~1e-16) and far below any real price difference (~1e-2).
    """
    e = problem.charge_energy
    if not np.isclose(problem.charge_energy, problem.discharge_energy):
        raise ValueError("DP grid requires charge_energy == discharge_energy (v1)")
    require_soc_on_grid(problem)

    t = problem.num_slots
    n_max = int(round(problem.capacity / e))
    k0 = int(round(problem.initial_soc / e))
    inf = np.inf
    # (delta level, GRID energy signed, delta actions) per action. The level step is
    # store-side and symmetric; the priced quantity is grid-side and is not, once
    # efficiencies differ -- so each move carries its own coefficient rather than a
    # shared +-e.
    moves = (
        (_IDLE, 0, 0.0, 0),
        (_CHARGE, +1, +problem.grid_charge_energy, 1),
        (_DISCHARGE, -1, -problem.grid_discharge_energy, 1),
    )

    def layer():
        return (np.full(n_max + 1, inf), np.full(n_max + 1, inf),
                np.zeros(n_max + 1, dtype=object), np.zeros(n_max + 1, dtype=object))

    # --- forward: best (cost, then actions) and both counts, to each level ---
    f_cost, f_act, f_all, f_min = [], [], [], []
    cost, act, n_all, n_min = layer()
    cost[k0], act[k0], n_all[k0], n_min[k0] = 0.0, 0, 1, 1
    for j in range(t):
        f_cost.append(cost); f_act.append(act); f_all.append(n_all); f_min.append(n_min)
        p = problem.price[j]
        cands = []
        for _, dk, dc, da in moves:
            c2, a2, all2, min2 = layer()
            src = slice(max(0, -dk), n_max + 1 - max(0, dk))
            dst = slice(max(0, dk), n_max + 1 - max(0, -dk))
            c2[dst] = cost[src] + dc * p
            a2[dst] = act[src] + da
            all2[dst], min2[dst] = n_all[src], n_min[src]
            cands.append((c2, a2, all2, min2))
        cost = np.min([c for c, _, _, _ in cands], axis=0)
        act = np.full(n_max + 1, inf)
        for c, a, _, _ in cands:
            m = np.isfinite(c) & (c <= cost + atol)
            act[m] = np.minimum(act[m], a[m])
        n_all, n_min = np.zeros(n_max + 1, dtype=object), np.zeros(n_max + 1, dtype=object)
        for c, a, q_all, q_min in cands:
            m = np.isfinite(c) & (c <= cost + atol)
            n_all[m] += q_all[m]
            n_min[m & (a <= act + atol)] += q_min[m & (a <= act + atol)]
        cost, act = np.where(np.isfinite(cost), cost, inf), act

    best_cost, best_act = float(cost[k0]), float(act[k0])
    if not np.isfinite(best_cost):
        raise ValueError("no feasible schedule returns to the initial state of charge")

    # --- backward: best (cost, actions) from each level onward to the terminal k0 ---
    b_cost, b_act = [None] * (t + 1), [None] * (t + 1)
    cost, act = np.full(n_max + 1, inf), np.full(n_max + 1, inf)
    cost[k0], act[k0] = 0.0, 0
    b_cost[t], b_act[t] = cost, act
    for j in range(t - 1, -1, -1):
        p = problem.price[j]
        nc, na = np.full(n_max + 1, inf), np.full(n_max + 1, inf)
        for _, dk, dc, da in moves:
            src = slice(max(0, dk), n_max + 1 - max(0, -dk))     # level k+dk
            dst = slice(max(0, -dk), n_max + 1 - max(0, dk))     # level k
            c2 = cost[src] + dc * p
            a2 = act[src] + da
            # An unreachable level is inf on both sides, and inf - inf is nan. Mask
            # the subtraction itself (numpy evaluates it before any boolean guard),
            # leaving inf where it is skipped so the tie test is simply False there.
            cur = nc[dst]
            both = np.isfinite(c2) & np.isfinite(cur)
            diff = np.full(c2.shape, inf)
            np.subtract(c2, cur, out=diff, where=both)
            better = np.isfinite(c2) & (c2 < cur - atol)
            tie = both & (np.abs(diff) <= atol) & (a2 < na[dst])
            take = better | tie
            ncd, nad = nc[dst].copy(), na[dst].copy()
            ncd[take], nad[take] = c2[take], a2[take]
            nc[dst], na[dst] = ncd, nad
        cost, act = nc, na
        b_cost[j], b_act[j] = cost, act

    # --- a (slot, action) is live iff some minimal optimum routes through it ---
    slot_actions = []
    for j in range(t):
        p = problem.price[j]
        live = []
        for action, dk, dc, da in moves:
            lo, hi = max(0, -dk), n_max - max(0, dk)
            if hi < lo:
                continue
            k = np.arange(lo, hi + 1)
            total = f_cost[j][k] + dc * p + b_cost[j + 1][k + dk]
            steps = f_act[j][k] + da + b_act[j + 1][k + dk]
            ok = (np.abs(total - best_cost) <= atol) & (np.abs(steps - best_act) <= atol)
            if bool(ok.any()):
                live.append(_ACTION_NAMES[action])
        slot_actions.append(tuple(live))

    return OptimaCensus(
        n_optima=int(n_all[k0]),
        n_minimal=int(n_min[k0]),
        min_actions=int(best_act),
        slot_actions=tuple(slot_actions),
    )
