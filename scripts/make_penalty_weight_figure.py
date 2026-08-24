"""Web figure: the penalty weight, drawn as the distribution it distorts.

`mass_ratio_exact.png` reports the penalty-weight finding as a summary statistic --
optimal-state mass over uniform random, one point per (T, reps) cell. That is the
right form for a sweep and the wrong form for a first look: it asks the reader to
accept that a ratio of two small numbers means something before they have seen what
the algorithm actually produces.

This figure shows the underlying object instead. For one instance, at one circuit
depth, it draws the **whole output distribution** -- how likely the circuit is to
hand you each possible battery schedule -- at the two penalty weights. Nothing else
differs: same problem, same encoding, same circuit, same optimizer, same seed. Only
the penalty scale.

The result is sharper than the ratio suggests. At the rule-of-thumb weight the
single most likely answer is a schedule that **charges and discharges in the same
hour** -- physically impossible -- and the best schedule is 80x less likely than it
should be. Rescaled to alpha*, the best schedule becomes the most likely output.

SLACK, AND THE TWO DEFENSIBLE NUMBERS. The QUBO carries slack bits that encode the
state-of-charge inequality; they are internal bookkeeping and are not part of the
schedule. So there are two honest ways to ask "how often does it return the best
answer":

  * P(best schedule) -- probability summed over the slack settings, i.e. decode the
    decision bits and ignore the rest. This is what a user of the solver receives,
    and it is what this figure plots: 0.0026 -> 0.2101, a factor of 80.
  * P(minimum-energy state) -- the same schedule AND its slack set consistently.
    This is the repo's committed `ideal_opt_mass` metric, reported everywhere else:
    0.0011 -> 0.1398, a factor of 131.

Both are stated on the figure. The script gates on the second -- it refuses to draw
unless it reproduces each arm's committed `ideal_opt_mass` from the committed tuned
angles -- so the drawn quantity cannot drift away from the recorded one.

WHY THIS CELL (T=2, seed 0, reps=2). Chosen for legibility, not for effect size:
2 slots is 16 distinct schedules, which is the largest number of bars that stays
readable. **Neither** arm hit the optimizer's evaluation budget, so neither value is
censored and no lower-bound caveat is needed. It is not the most extreme cell in
the sweep. The most extreme is T=3, seed 1, reps=2 -- the cell LESSONS.md Sec. 3
quotes -- where the default weight puts 6.8e-6 of the mass on the minimum-energy
state against alpha*'s 1.52e-2, a factor of 2231. That cell has 1024 outcomes and
its alpha* arm is censored, so it is quoted here rather than drawn.

HONEST FRAMING, ON THE FIGURE. This is not a claim of quantum advantage. `dp_solve`
returns the exact optimum for this instance in microseconds. The right panel shows a
quantum state concentrating on good answers at all, which is a precondition for any
future advantage and not evidence of one. The left panel shows that a standard
penalty-weight heuristic destroys that concentration -- and *that* is the
transferable result, because it applies to any constrained problem handed to a
variational quantum algorithm.

Probabilities are exact statevector values (`quantum_solar.statevector`), not
sampled: no shot noise, no 1/4096 floor.

Run:  python scripts/make_penalty_weight_figure.py
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from experiment_scaling import (  # noqa: E402
    CAPACITY,
    CHARGE_ENERGY,
    INITIAL_SOC,
    RESULTS_DIR,
    alpha_star,
    scaled,
)
from quantum_solar import build_qubo, default_weights, dp_solve, synthetic_instance  # noqa: E402
from quantum_solar.brute_force import enumerate_bitstrings  # noqa: E402
from quantum_solar.statevector import assert_matches_qiskit, qaoa_probabilities  # noqa: E402

OUT = (Path(__file__).resolve().parent.parent / "docs" / "figures" / "web"
       / "penalty_weight.png")

# The drawn cell. See "WHY THIS CELL" above.
T, SEED, REPS = 2, 0, 2

ARMS = [
    # The overshoot factor in the left subtitle is 1/alpha*, computed for the drawn
    # cell rather than quoted: alpha* is per-instance (0.0217 here, 0.0209 on the
    # T=3 instance LESSONS.md Sec. 1 works through), so a hard-coded "48x" would be
    # right for that write-up and wrong for this panel.
    ("default", "qaoa_scaling_T5.csv",
     "Penalty weight from the usual rule of thumb",
     "constraint penalties ~{overshoot:.0f}x the span of the electricity cost"),
    ("alphastar", "qaoa_scaling_alphastar_T5.csv",
     "Penalty weight set to $\\alpha^*$",
     "the threshold derivable from the problem before running anything"),
]

# Reproduce the committed ideal_opt_mass from the committed angles to this
# tolerance, or refuse to draw. The slack is for float formatting in the CSV
# (`params` is written at 9 significant figures), not for genuine drift.
REPRO_ATOL = 1e-8

OPTIMAL = "#E45756"    # the cost-optimal schedule
FEASIBLE = "#4C78A8"   # other schedules the battery can actually run
INFEASIBLE = "0.72"    # outcomes that violate its physical limits


def _row(csv_name: str) -> dict:
    """The one sweep row for the drawn cell."""
    for r in csv.DictReader(open(RESULTS_DIR / csv_name)):
        if (int(r["T"]), int(r["seed"]), int(r["reps"])) == (T, SEED, REPS):
            return r
    raise SystemExit(f"cell T={T} seed={SEED} reps={REPS} not found in {csv_name}")


def _arm(mode, csv_name, problem, base, a_star, schedule_id):
    """Per-schedule probabilities for one penalty weight, gated on the committed value.

    Returns (per_schedule_probs, state_mass) where ``state_mass`` is the committed
    ``ideal_opt_mass`` metric -- probability on the minimum-energy basis state,
    slack included -- recomputed here and checked against the CSV.
    """
    row = _row(csv_name)
    weights = base if mode == "default" else scaled(base, a_star)
    qubo = build_qubo(problem, weights)
    m = qubo.num_vars

    x = enumerate_bitstrings(m).astype(float)
    # A constant shift of the diagonal is a global phase, so raw QUBO energies
    # serve directly as the cost diagonal (see quantum_solar.statevector).
    energy = np.einsum("bi,ij,bj->b", x, qubo.Q, x) + qubo.offset
    params = [float(v) for v in row["params"].split(";")]
    probs = qaoa_probabilities(energy, params, REPS)

    state_mass = float(probs[np.isclose(energy, energy.min(), atol=1e-6)].sum())
    committed = float(row["ideal_opt_mass"])
    if abs(state_mass - committed) > REPRO_ATOL:
        raise SystemExit(
            f"REFUSING TO DRAW: the {mode} arm recomputes ideal_opt_mass="
            f"{state_mass:.10f} from the committed angles, but {csv_name} records "
            f"{committed:.10f} (delta {abs(state_mass - committed):.2e} > "
            f"{REPRO_ATOL:.0e}). The figure and the sweep have diverged."
        )
    if row["evals_censored"] == "True":
        raise SystemExit(
            f"REFUSING TO DRAW: the {mode} arm is evals_censored, so its mass is a "
            f"lower bound and the panel would overstate its own precision."
        )

    per_schedule = np.zeros(2 ** (2 * T))
    np.add.at(per_schedule, schedule_id, probs)
    return per_schedule, state_mass


def _label(bits) -> str:
    """One character per slot: C charge, D discharge, . idle, X both (illegal)."""
    c, d = bits[:T], bits[T:2 * T]
    return "".join("X" if ci and di else "C" if ci else "D" if di else "."
                   for ci, di in zip(c, d))


def main() -> None:
    problem = synthetic_instance(T, seed=SEED, capacity=CAPACITY,
                                 charge_energy=CHARGE_ENERGY, initial_soc=INITIAL_SOC)
    base = default_weights(problem)
    a_star = alpha_star(problem, base)
    dp = dp_solve(problem)

    n_sched = 2 ** (2 * T)
    m = build_qubo(problem, base).num_vars
    decision = enumerate_bitstrings(m)[:, :2 * T]
    schedule_id = decision @ (1 << np.arange(2 * T))

    # One representative bitstring per schedule id, for feasibility and true cost.
    rep = np.zeros((n_sched, 2 * T), dtype=np.int8)
    rep[schedule_id] = decision
    feasible = np.array([problem.is_feasible(b) for b in rep])
    true_cost = np.array([problem.energy(b) for b in rep])

    # Standing convention: a script reporting NumPy-statevector numbers gates on
    # the Qiskit cross-check first (docs/ARCHITECTURE.md). Cheap at m=6, which is
    # a size where the Qiskit path still works at all.
    from quantum_solar import qubo_to_ising

    operator, _const = qubo_to_ising(build_qubo(problem, base))
    delta = assert_matches_qiskit(operator, [0.31, 0.62, 1.23, 0.45], reps=REPS)
    print(f"statevector cross-check vs Qiskit: max |dP| = {delta:.2e}")

    arms = [(title, sub.format(overshoot=1.0 / a_star))
            + _arm(mode, csv, problem, base, a_star, schedule_id)
            for mode, csv, title, sub in ARMS]

    # Shared ordering: feasible schedules first, cheapest to most expensive, then
    # the infeasible ones. It is a property of the problem, not of either penalty
    # weight, so the panels line up bar for bar.
    order = np.concatenate([
        np.flatnonzero(feasible)[np.argsort(true_cost[feasible], kind="stable")],
        np.flatnonzero(~feasible)[np.argsort(true_cost[~feasible], kind="stable")],
    ])
    n_feasible = int(feasible.sum())
    assert np.isclose(true_cost[order[0]], dp.true_energy, atol=1e-9), \
        "leftmost bar is not the DP optimum"

    labels = [_label(rep[i]) for i in order]
    uniform = 1.0 / n_sched
    ratio = arms[1][2][order[0]] / arms[0][2][order[0]]

    fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), sharey=True)
    for ax, (title, subtitle, per_schedule, state_mass) in zip(axes, arms):
        y = per_schedule[order]
        colors = [INFEASIBLE] * n_sched
        for i in range(n_feasible):
            colors[i] = FEASIBLE
        colors[0] = OPTIMAL

        ax.axvspan(n_feasible - 0.5, n_sched - 0.5, color="0.955", zorder=0)
        ax.bar(np.arange(n_sched), y, width=0.82, color=colors, zorder=2)
        ax.axhline(uniform, color="0.35", ls="--", lw=1.2, zorder=3)

        ax.set_xticks(np.arange(n_sched))
        ax.set_xticklabels(labels, fontsize=8.5, family="monospace")
        for tick, i in zip(ax.get_xticklabels(), order):
            tick.set_color(OPTIMAL if i == order[0] else
                           "0.25" if feasible[i] else "0.55")
        ax.set_xlim(-0.7, n_sched - 0.3)
        ax.set_title(f"{title}\n{subtitle}", fontsize=12)
        ax.text(0.5, -0.155, "each bar is one 2-hour plan   (C charge · D discharge · "
                             ". idle · X both at once)",
                transform=ax.transAxes, ha="center", fontsize=8.5, color="0.45")

        top = int(np.argmax(y))
        ax.annotate(
            (f"most likely answer\ncharges and discharges\nin the same hour\nP = {y[top]:.3f}"
             if not feasible[order[top]] else
             f"most likely answer\nis the best schedule\nP = {y[top]:.3f}"),
            xy=(top, y[top]), xytext=(top + 1.4, y[top] * 0.97),
            fontsize=9.5, va="top", ha="left",
            color=("0.35" if not feasible[order[top]] else OPTIMAL),
            weight=("normal" if not feasible[order[top]] else "bold"),
            arrowprops=dict(arrowstyle="->", lw=1.4,
                            color=("0.45" if not feasible[order[top]] else OPTIMAL)),
        )
        if top != 0:
            # Clear the neighboring bars: drop in from above and to the right,
            # rather than crossing whatever the circuit did concentrate on.
            ax.annotate(
                f"best schedule\nP = {y[0]:.4f}",
                xy=(0, y[0]), xytext=(2.6, y.max() * 0.60),
                fontsize=9.5, color=OPTIMAL, weight="bold", va="bottom",
                arrowprops=dict(arrowstyle="->", color=OPTIMAL, lw=1.4,
                                connectionstyle="arc3,rad=0.2"),
            )
        ax.text(n_sched - 0.5, uniform * 1.06,
                "  uniform random guessing", ha="right", va="bottom",
                fontsize=8.5, color="0.35")

    axes[0].set_ylabel("probability the circuit hands you this plan")

    fig.suptitle(
        f"Same problem, same circuit, one number changed: {ratio:.0f}x more "
        f"probability on the best schedule",
        fontsize=14.5, y=0.995,
    )
    fig.legend(
        handles=[
            Patch(color=OPTIMAL, label="the cost-optimal schedule"),
            Patch(color=FEASIBLE, label=f"other plans the battery can run ({n_feasible - 1})"),
            Patch(color=INFEASIBLE, label=f"plans that violate its physical limits ({n_sched - n_feasible})"),
        ],
        loc="lower center", ncol=3, fontsize=9.5, frameon=False,
        bbox_to_anchor=(0.5, 0.085),
    )
    fig.tight_layout(rect=(0, 0.185, 1, 0.955))

    note = (
        f"Battery scheduling over {T} time slots, encoded as a QUBO on {m} qubits and "
        f"solved with {REPS}-layer QAOA. Exact statevector probabilities: no shot noise, "
        f"no sampling floor. The panels share every input except the penalty scale.\n"
        f"Bars sum probability over the encoding's internal slack bits. Requiring those "
        f"to be set consistently too (the metric reported elsewhere in this repo), the "
        f"same comparison is {arms[0][3]:.4f} → {arms[1][3]:.4f}, a factor of "
        f"{arms[1][3] / arms[0][3]:.0f}.\n"
        f"Not a claim of quantum advantage: the exact classical solver returns this "
        f"optimum in microseconds. It shows a standard penalty-weight heuristic stopping "
        f"the circuit concentrating on the answer at all."
    )
    fig.text(0.5, 0.030, note, ha="center", fontsize=10, color="0.35")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=140, bbox_inches="tight")
    print(f"wrote {OUT}")
    print(f"  cell T={T} seed={SEED} reps={REPS}, m={m} qubits, alpha*={a_star:.6f}")
    for (title, _sub, per_schedule, state_mass), (mode, *_ ) in zip(arms, ARMS):
        print(f"  {mode:9s} P(best schedule)={per_schedule[order[0]]:.6f}   "
              f"P(min-energy state)={state_mass:.6f}  [committed value reproduced]")
    print(f"  ratio: {ratio:.1f}x on the schedule, "
          f"{arms[1][3] / arms[0][3]:.1f}x on the minimum-energy state")


if __name__ == "__main__":
    main()
