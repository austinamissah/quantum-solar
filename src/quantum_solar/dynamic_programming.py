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

import numpy as np

from .problem import BatteryProblem
from .solution import Solution

_IDLE, _CHARGE, _DISCHARGE = 0, 1, 2


def dp_solve(problem: BatteryProblem) -> Solution:
    """Return the exact cost-minimizing schedule as a :class:`Solution`."""
    e = problem.charge_energy
    if not np.isclose(problem.charge_energy, problem.discharge_energy):
        raise ValueError("DP grid requires charge_energy == discharge_energy (v1)")

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
        idle = cost                                   # k <- k
        charge = np.full(n_max + 1, inf)
        charge[1:] = cost[:-1] + p * problem.charge_energy      # k <- k-1
        discharge = np.full(n_max + 1, inf)
        discharge[:-1] = cost[1:] - p * problem.discharge_energy  # k <- k+1

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
