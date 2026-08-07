"""Exact dynamic-programming solver — the scalable classical baseline.

The state of charge lives on a discrete grid ``{0, g, 2g, …, Q}``, where ``g`` is
the greatest common divisor of the charge and discharge energies
(:func:`~quantum_solar.problem.soc_quantum`) — just the shared rate when they are
equal. A charging slot climbs ``charge_energy/g`` levels and a discharging slot
falls ``discharge_energy/g``, so a schedule is still a path over a uniform grid and
the optimum is found by dynamic programming in ``O(T·K·3)`` time (``K`` SoC levels,
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

from .problem import BatteryProblem, require_soc_on_grid, soc_quantum
from .solution import Solution

_IDLE, _CHARGE, _DISCHARGE = 0, 1, 2
_ACTION_NAMES = ("idle", "charge", "discharge")

#: Tolerance for calling two costs equal when breaking ties. Same classifier, and
#: the same reasoning, as :func:`optima_census`: far above float64 accumulation
#: error over a day (~1e-16) and far below any real price difference (~1e-2).
TIE_ATOL = 1e-9


def dp_solve(problem: BatteryProblem, *, atol: float = TIE_ATOL) -> Solution:
    """Return the exact cost-minimizing schedule as a :class:`Solution`.

    **Tie-break (specified, not incidental).** The optimum is usually far from
    unique — every hour at the same price is interchangeable — so *which* optimal
    schedule comes back has to be pinned or it is not reproducible. Selection is
    lexicographic:

    1. minimum cost (within ``atol``);
    2. then the **fewest battery actions** (charges + discharges);
    3. then a fixed action preference, idle < charge < discharge.

    Step 2 is what makes the returned plan meaningful rather than merely optimal.
    In a lossless model a charge and a discharge at the same price cancel exactly,
    so cost alone leaves unlimited free cycling tied for the optimum — on a
    flat-price day *every* feasible schedule ties (~1.5e10 of them). Without a
    tie-break on action count the solver may return any of that churn, which reads
    as a plan and is noise. With it, the flat day comes back idle, as it should.

    The guarantee this buys, asserted in ``tests/test_dynamic_programming.py``:
    the returned schedule uses exactly ``optima_census(problem).min_actions``
    actions, so it is always a member of the population ``optima_census``
    describes. Reporting ``dp_solve``'s hours next to the census's ``forced()``
    is therefore consistent by construction.

    It is still only *one* of the tied minimal optima (``n_minimal`` of them), so
    the caller's obligation is unchanged: report ``forced()``, never the raw hour
    list. What is new is that re-running cannot silently hand back a different
    plan — which is how four committed figures drifted once already.
    """
    require_soc_on_grid(problem)

    t = problem.num_slots
    e = soc_quantum(problem)
    n_max = int(round(problem.capacity / e))
    k0 = int(round(problem.initial_soc / e))
    # Levels moved per action. Equal (both 1 after scaling) in the symmetric case;
    # asymmetric rates simply span different numbers of levels on a finer grid.
    up = int(round(problem.charge_energy / e))
    down = int(round(problem.discharge_energy / e))
    inf = np.inf

    # Forward DP: cost[k] = min cost to reach SoC level k after the processed slots,
    # and steps[k] = the fewest actions among the paths achieving that cost. Both
    # are additive, so tracking them together is an ordinary lexicographic shortest
    # path: a min-cost min-action path's prefixes are themselves min-cost, and
    # min-action among those.
    cost = np.full(n_max + 1, inf)
    cost[k0] = 0.0
    steps = np.full(n_max + 1, inf)
    steps[k0] = 0.0
    actions = np.zeros((t, n_max + 1), dtype=np.int8)  # chosen action to land on k

    # Per-slot cost of each action relative to idling. This is where losses and an
    # export price below the import price are priced; the SoC step below stays
    # store-side. Costs remain per-(slot, action) even when the bill is piecewise,
    # because the household's net is exogenous — which is why the DP still applies.
    idle_cost, charge_delta, discharge_delta, _ = problem.action_costs()

    for j in range(t):
        charge = np.full(n_max + 1, inf)
        charge[up:] = cost[:n_max + 1 - up] + charge_delta[j]        # k <- k-up
        charge_steps = np.full(n_max + 1, inf)
        charge_steps[up:] = steps[:n_max + 1 - up] + 1
        discharge = np.full(n_max + 1, inf)
        discharge[:n_max + 1 - down] = cost[down:] + discharge_delta[j]  # k <- k+down
        discharge_steps = np.full(n_max + 1, inf)
        discharge_steps[:n_max + 1 - down] = steps[down:] + 1

        # Row order IS the third tie-break level: idle < charge < discharge.
        cand_cost = np.vstack([cost, charge, discharge])              # idle: k <- k
        cand_steps = np.vstack([steps, charge_steps, discharge_steps])

        best_cost = cand_cost.min(axis=0)
        # Compare within atol rather than exactly. An exact `<` is what let a
        # refactor that moved costs by ~1e-16 silently reorder the ties and rewrite
        # every committed figure; a tolerance makes the choice depend on the prices,
        # not on the order the arithmetic happened to be done in.
        tied = np.isfinite(cand_cost) & (cand_cost <= best_cost + atol)
        tied_steps = np.where(tied, cand_steps, inf)
        best_steps = tied_steps.min(axis=0)
        # argmax on a boolean picks the FIRST True, giving the row-order preference.
        # Unreachable levels are all-False and fall through to idle, which is never
        # routed through: reconstruction only visits levels reachable from k0.
        actions[j] = np.argmax(tied & (tied_steps <= best_steps + atol), axis=0)
        cost, steps = best_cost, best_steps

    # Terminal constraint: must end at the initial SoC level. The accumulated cost
    # is relative to idling, so add the idle bill back.
    total = float(cost[k0] + idle_cost.sum())

    # Reconstruct the schedule backward from k0.
    c = np.zeros(t, dtype=np.int8)
    d = np.zeros(t, dtype=np.int8)
    k = k0
    for j in range(t - 1, -1, -1):
        action = actions[j, k]
        if action == _CHARGE:
            c[j] = 1
            k -= up
        elif action == _DISCHARGE:
            d[j] = 1
            k += down
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
    require_soc_on_grid(problem)

    t = problem.num_slots
    e = soc_quantum(problem)
    n_max = int(round(problem.capacity / e))
    k0 = int(round(problem.initial_soc / e))
    up = int(round(problem.charge_energy / e))
    down = int(round(problem.discharge_energy / e))
    inf = np.inf
    # (delta level, PER-SLOT cost array relative to idling, delta actions). The level
    # step is store-side and symmetric; the cost is not, once efficiencies differ or
    # export is credited below import -- and it varies by slot, so each move carries
    # its own (T,) array rather than a shared scalar.
    idle_cost, charge_delta, discharge_delta, _ = problem.action_costs()
    moves = (
        (_IDLE, 0, np.zeros(t), 0),
        (_CHARGE, +up, charge_delta, 1),
        (_DISCHARGE, -down, discharge_delta, 1),
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
        cands = []
        for _, dk, dc, da in moves:
            c2, a2, all2, min2 = layer()
            src = slice(max(0, -dk), n_max + 1 - max(0, dk))
            dst = slice(max(0, dk), n_max + 1 - max(0, -dk))
            c2[dst] = cost[src] + dc[j]
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
        nc, na = np.full(n_max + 1, inf), np.full(n_max + 1, inf)
        for _, dk, dc, da in moves:
            src = slice(max(0, dk), n_max + 1 - max(0, -dk))     # level k+dk
            dst = slice(max(0, -dk), n_max + 1 - max(0, dk))     # level k
            c2 = cost[src] + dc[j]
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
        live = []
        for action, dk, dc, da in moves:
            lo, hi = max(0, -dk), n_max - max(0, dk)
            if hi < lo:
                continue
            k = np.arange(lo, hi + 1)
            total = f_cost[j][k] + dc[j] + b_cost[j + 1][k + dk]
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
