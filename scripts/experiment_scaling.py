"""QAOA-vs-exact scaling experiment for battery-scheduling QUBOs.

Sweeps synthetic instances of increasing size, solves each with QAOA (on the Aer
simulator) and with the exact classical baselines (DP always; brute force as an
independent cross-check while the qubit count stays within the enumeration cap),
and records how QAOA's solution quality and runtime scale against DP's exact,
microsecond-scale optimum.

Reproducible and seeded. ONE fixed configuration is used across the whole sweep
(chosen before seeing results): no per-instance tuning of penalty weights or
optimizer settings, and every configured run is recorded — failures included.

Run the full sweep:  python scripts/experiment_scaling.py
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import numpy as np

from quantum_solar import (
    QAOASolver,
    brute_force_solve,
    build_qubo,
    default_weights,
    dp_solve,
    synthetic_instance,
)
from quantum_solar.brute_force import MAX_ENUMERATION_SITES

# --- Fixed sweep configuration (chosen before results) -----------------------
T_VALUES = [2, 3, 4, 5, 6]        # qubits m = 4T-2 -> 6, 10, 14, 18, 22
SEEDS = [0, 1, 2]                 # 3 instances per T
REPS_VALUES = [1, 2, 3]           # QAOA layers
QAOA_SEED = 1234                  # fixed: seeds Aer + restart RNG
N_STARTS = 5                      # QAOASolver default
SHOTS = 4096                      # QAOASolver default
MAXITER = 200                     # COBYLA default
CAPACITY = 3.0
CHARGE_ENERGY = 1.0
INITIAL_SOC = 1.0

RESULTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "results"
CSV_PATH = RESULTS_DIR / "qaoa_scaling.csv"

FIELDNAMES = [
    "T", "m", "seed", "reps", "dp_cost", "qaoa_cost", "exact_match",
    "gap_abs", "gap_pct", "opt_prob_mass", "feasibility_rate",
    "qaoa_time_s", "dp_time_s", "brute_cost", "brute_matches_dp",
    "n_starts", "shots",
]

# Post-hoc uniform-random-sampling baseline columns (added after the sweep).
UNIFORM_FIELDS = [
    "uniform_opt_mass", "uniform_best_cost", "mass_ratio",
    "mass_ratio_is_upper_bound", "shots_cover_space",
]
AUG_FIELDNAMES = FIELDNAMES + UNIFORM_FIELDS


def _key_to_x(key: str, m: int) -> np.ndarray:
    bits = key.replace(" ", "")
    return np.array([int(bits[m - 1 - i]) for i in range(m)], dtype=np.int8)


def _mass_and_feasibility(problem, qubo, counts, optimum_energy):
    """Empirical prob. mass on optimal bitstrings + feasibility rate (from shots)."""
    total = sum(counts.values())
    m = qubo.num_vars
    opt = 0
    feas = 0
    for key, n in counts.items():
        x = _key_to_x(key, m)
        if problem.is_feasible(x):
            feas += n
        if np.isclose(qubo.energy(x), optimum_energy, atol=1e-6):
            opt += n
    return opt / total, feas / total


def run_single(T, seed, reps, *, n_starts, shots, maxiter, qaoa_seed):
    """Run one (T, seed, reps) cell and return its metrics row."""
    problem = synthetic_instance(
        T, seed=seed, capacity=CAPACITY, charge_energy=CHARGE_ENERGY,
        initial_soc=INITIAL_SOC,
    )
    weights = default_weights(problem)  # fixed principled rule, applied uniformly
    qubo = build_qubo(problem, weights)
    m = qubo.num_vars

    t0 = time.perf_counter()
    dp = dp_solve(problem)
    dp_time = time.perf_counter() - t0
    dp_cost = dp.true_energy  # == the QUBO global minimum energy

    brute_cost = float("nan")
    brute_matches = ""
    if m <= MAX_ENUMERATION_SITES:
        brute = brute_force_solve(problem, qubo)
        brute_cost = brute.true_energy
        brute_matches = bool(np.isclose(brute_cost, dp_cost, atol=1e-6))
        assert brute_matches, f"exact solvers disagree at T={T} seed={seed}"

    solver = QAOASolver(reps=reps, n_starts=n_starts, shots=shots,
                        seed=qaoa_seed, maxiter=maxiter)
    t0 = time.perf_counter()
    result = solver.solve(problem, qubo)
    qaoa_time = time.perf_counter() - t0

    qaoa_cost = result.true_energy  # cost of the best-sampled schedule
    exact = bool(result.feasible and np.isclose(qaoa_cost, dp_cost, atol=1e-6))
    if result.feasible:
        gap_abs = qaoa_cost - dp_cost
        gap_pct = gap_abs / abs(dp_cost) * 100.0 if abs(dp_cost) > 1e-9 else float("nan")
    else:
        gap_abs = float("nan")  # infeasible "best" has no meaningful gap
        gap_pct = float("nan")

    opt_mass, feas_rate = _mass_and_feasibility(problem, qubo, result.counts, dp_cost)

    return {
        "T": T, "m": m, "seed": seed, "reps": reps,
        "dp_cost": dp_cost, "qaoa_cost": qaoa_cost, "exact_match": exact,
        "gap_abs": gap_abs, "gap_pct": gap_pct,
        "opt_prob_mass": opt_mass, "feasibility_rate": feas_rate,
        "qaoa_time_s": qaoa_time, "dp_time_s": dp_time,
        "brute_cost": brute_cost, "brute_matches_dp": brute_matches,
        "n_starts": n_starts, "shots": shots,
    }


def run_experiment(t_values=T_VALUES, seeds=SEEDS, reps_values=REPS_VALUES, *,
                   n_starts=N_STARTS, shots=SHOTS, maxiter=MAXITER,
                   qaoa_seed=QAOA_SEED, progress=False):
    """Run the full sweep and return a list of metric rows (every run recorded)."""
    rows = []
    for T in t_values:
        for seed in seeds:
            for reps in reps_values:
                row = run_single(T, seed, reps, n_starts=n_starts, shots=shots,
                                  maxiter=maxiter, qaoa_seed=qaoa_seed)
                rows.append(row)
                if progress:
                    print(f"T={T} m={row['m']} seed={seed} reps={reps} "
                          f"exact={row['exact_match']} "
                          f"mass={row['opt_prob_mass']:.3f} "
                          f"feas={row['feasibility_rate']:.3f} "
                          f"t={row['qaoa_time_s']:.1f}s", flush=True)
    return rows


def run_and_stream(t_values=T_VALUES, seeds=SEEDS, reps_values=REPS_VALUES, *,
                   n_starts=N_STARTS, shots=SHOTS, maxiter=MAXITER,
                   qaoa_seed=QAOA_SEED, csv_path=CSV_PATH):
    """Run the sweep serially, appending each row to the CSV as it completes.

    Serial by design: QAOA statevector simulation is memory-bandwidth bound, so
    running instances concurrently saturates the memory bus (~no speedup) AND
    inflates the per-run QAOA timings we report. One run at a time uses all cores
    with full bandwidth, giving clean, comparable runtimes. The CSV is written
    incrementally (crash-resilient); rows are already in sweep order.
    """
    configs = [(T, s, r) for T in t_values for s in seeds for r in reps_values]
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=FIELDNAMES).writeheader()

    rows = []
    total = len(configs)
    for i, (T, seed, reps) in enumerate(configs, 1):
        row = run_single(T, seed, reps, n_starts=n_starts, shots=shots,
                         maxiter=maxiter, qaoa_seed=qaoa_seed)
        rows.append(row)
        with open(csv_path, "a", newline="") as f:
            csv.DictWriter(f, fieldnames=FIELDNAMES).writerow(row)
        print(f"[{i}/{total}] T={T} m={row['m']} seed={seed} reps={reps} "
              f"exact={row['exact_match']} mass={row['opt_prob_mass']:.3f} "
              f"feas={row['feasibility_rate']:.3f} t={row['qaoa_time_s']:.1f}s", flush=True)
    return rows


def write_csv(rows, path=CSV_PATH, fieldnames=FIELDNAMES):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def load_results(path=CSV_PATH):
    """Load a results CSV back into typed rows (numpy/stdlib only, no pandas).

    Tolerant of the base or the uniform-augmented schema.
    """
    int_cols = {"T", "m", "seed", "reps", "n_starts", "shots"}
    float_cols = {"dp_cost", "qaoa_cost", "gap_abs", "gap_pct", "opt_prob_mass",
                  "feasibility_rate", "qaoa_time_s", "dp_time_s", "brute_cost",
                  "uniform_opt_mass", "uniform_best_cost", "mass_ratio"}
    bool_cols = {"exact_match", "mass_ratio_is_upper_bound", "shots_cover_space"}
    tri_cols = {"brute_matches_dp"}
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            for k, v in list(r.items()):
                if k in int_cols:
                    r[k] = int(v)
                elif k in float_cols:
                    r[k] = float(v) if v not in ("", "nan") else float("nan")
                elif k in bool_cols:
                    r[k] = v in ("True", "true", "1")
                elif k in tri_cols:
                    r[k] = (True if v == "True" else False if v == "False" else None)
            rows.append(r)
    return rows


def _schedule_costs(problem, X):
    """Vectorized true schedule cost for a stack of bitstrings (decision bits)."""
    t = problem.num_slots
    charge = X[:, :t]
    discharge = X[:, t:2 * t]
    const = float(problem.price @ (problem.load - problem.generation))
    return (const
            + charge @ (problem.price * problem.charge_energy)
            - discharge @ (problem.price * problem.discharge_energy))


def uniform_baseline(problem, qubo, shots):
    """Exact uniform-sampling baseline from full enumeration.

    Returns (uniform_opt_mass, expected_best_cost):
      * uniform_opt_mass = (# optimal bitstrings) / 2^m — the exact probability a
        single uniform draw is optimal.
      * expected_best_cost — the expected TRUE COST of the min-energy sample among
        `shots` uniform draws, mirroring the sweep's ``qaoa_cost`` (cost of the
        min-QUBO-energy sampled bitstring). Using the same selection rule is what
        makes the QAOA-vs-uniform comparison fair. Computed exactly by order
        statistics: grouping bitstrings by energy, best-of-shots lands on a level
        with probability P(min>=level) - P(min>=next level), and that level's
        cost weight is its mean cost. No Monte Carlo. (Validated against an
        independent MC in tests.)

    Future work: a "best *feasible* schedule cost" baseline is also defensible,
    but only if reported symmetrically for QAOA as well; not computed here.
    """
    from quantum_solar.brute_force import enumerate_bitstrings

    m = qubo.num_vars
    X = enumerate_bitstrings(m).astype(float)
    energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
    costs = _schedule_costs(problem, X)
    N = 2 ** m

    n_opt = int(np.sum(np.isclose(energies, energies.min(), atol=1e-6)))
    uniform_opt_mass = n_opt / N

    # Group by energy level (ascending); best-of-shots lands on level j with
    # probability P(min>=level j) - P(min>=level j+1).
    key = np.round(energies, 6)
    order = np.argsort(key, kind="stable")
    ek, ck = key[order], costs[order]
    _, starts, counts = np.unique(ek, return_index=True, return_counts=True)
    cum = np.cumsum(counts)
    before = cum - counts
    p_level = ((N - before) / N) ** shots - ((N - cum) / N) ** shots
    mean_cost = np.add.reduceat(ck, starts) / counts
    expected_best_cost = float(np.sum(mean_cost * p_level))
    return uniform_opt_mass, expected_best_cost


def add_uniform_baseline(rows, *, shots=SHOTS):
    """Augment sweep rows with the uniform baseline and QAOA/uniform mass ratio.

    Observed optimal mass of 0 is below the shot-noise floor (1/shots); at those
    points the reported mass_ratio uses 1/shots and is an UPPER BOUND.
    """
    cache = {}
    for r in rows:
        T, seed, m = r["T"], r["seed"], r["m"]
        r["shots_cover_space"] = (2 ** m <= shots)
        if m > MAX_ENUMERATION_SITES:  # not enumerable (T=6): no uniform baseline
            r["uniform_opt_mass"] = float("nan")
            r["uniform_best_cost"] = float("nan")
            r["mass_ratio"] = float("nan")
            r["mass_ratio_is_upper_bound"] = False
            continue
        if (T, seed) not in cache:
            problem = synthetic_instance(T, seed=seed, capacity=CAPACITY,
                                         charge_energy=CHARGE_ENERGY, initial_soc=INITIAL_SOC)
            qubo = build_qubo(problem, default_weights(problem))
            cache[(T, seed)] = uniform_baseline(problem, qubo, shots)
        u_mass, u_cost = cache[(T, seed)]
        below_floor = (r["opt_prob_mass"] == 0.0)
        effective = (1.0 / shots) if below_floor else r["opt_prob_mass"]
        r["uniform_opt_mass"] = u_mass
        r["uniform_best_cost"] = u_cost
        r["mass_ratio"] = effective / u_mass if u_mass > 0 else float("nan")
        r["mass_ratio_is_upper_bound"] = below_floor
    return rows


# --- Plots -------------------------------------------------------------------

def _by_reps_T(rows, key, agg=np.mean):
    Ts = sorted({r["T"] for r in rows})
    reps_vals = sorted({r["reps"] for r in rows})
    series = {}
    for reps in reps_vals:
        series[reps] = [agg([r[key] for r in rows if r["T"] == T and r["reps"] == reps])
                        for T in Ts]
    return Ts, reps_vals, series


def plot_success_rate(rows):
    import matplotlib.pyplot as plt
    Ts, reps_vals, series = _by_reps_T(
        rows, "exact_match", agg=lambda v: float(np.mean([1.0 if x else 0.0 for x in v])))
    fig, ax = plt.subplots(figsize=(8, 5))
    for reps in reps_vals:
        ax.plot(Ts, series[reps], marker="o", label=f"reps={reps}")
    ax.set_xticks(Ts)
    ax.set_ylim(-0.05, 1.05)
    ax.set_xlabel("T (time slots)")
    ax.set_ylabel("exact-match rate (over seeds)")
    ax.set_title("QAOA exact-match success rate vs T")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_optimal_mass(rows):
    import matplotlib.pyplot as plt
    Ts, reps_vals, means = _by_reps_T(rows, "opt_prob_mass", agg=np.mean)
    _, _, los = _by_reps_T(rows, "opt_prob_mass", agg=np.min)
    _, _, his = _by_reps_T(rows, "opt_prob_mass", agg=np.max)
    fig, ax = plt.subplots(figsize=(8, 5))
    for reps in reps_vals:
        line, = ax.plot(Ts, means[reps], marker="o", label=f"reps={reps}")
        ax.fill_between(Ts, los[reps], his[reps], alpha=0.15, color=line.get_color())
    ax.set_xticks(Ts)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("T (time slots)")
    ax.set_ylabel("prob. mass on optimal bitstrings (4096 shots)")
    ax.set_title("QAOA optimal-probability-mass vs T (band = seed min/max)")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_runtime_qubits(rows):
    import matplotlib.pyplot as plt
    Ts, reps_vals, qaoa_t = _by_reps_T(rows, "qaoa_time_s", agg=np.mean)
    dp_t = [np.mean([r["dp_time_s"] for r in rows if r["T"] == T]) for T in Ts]

    fig, ax = plt.subplots(figsize=(8, 5))
    for reps in reps_vals:
        ax.plot(Ts, qaoa_t[reps], marker="o", label=f"QAOA reps={reps}")
    ax.plot(Ts, dp_t, marker="s", color="k", label="DP (exact)")
    ax.set_yscale("log")
    ax.set_xticks(Ts)
    ax.set_xlabel("T (time slots)")
    ax.set_ylabel("wall-clock time (s, log)")
    ax.set_title("Runtime and qubit count vs T")
    ax.legend(loc="center left", fontsize=8)

    ax2 = ax.twinx()
    ms = [4 * T - 2 for T in Ts]
    ax2.plot(Ts, ms, color="0.5", ls="--", marker="^", label="qubits (m=4T-2)")
    ax2.axhline(30, color="crimson", ls=":", lw=1.2)
    ax2.text(Ts[0], 30.3, "~30-qubit statevector limit (T≈8)",
             color="crimson", va="bottom", fontsize=8)
    ax2.set_ylabel("qubit count  m = 4T - 2")
    ax2.set_ylim(0, 34)
    fig.tight_layout()
    return fig


def plot_mass_ratio(rows):
    """QAOA optimal mass relative to uniform sampling (ratio > 1 beats random)."""
    import matplotlib.pyplot as plt
    rows = [r for r in rows if not np.isnan(r.get("mass_ratio", float("nan")))]
    Ts = sorted({r["T"] for r in rows})
    reps_vals = sorted({r["reps"] for r in rows})
    fig, ax = plt.subplots(figsize=(8, 5))
    for reps in reps_vals:
        xs, ys, ub = [], [], []
        for T in Ts:
            g = [r for r in rows if r["T"] == T and r["reps"] == reps]
            if not g:
                continue
            xs.append(T)
            ys.append(float(np.mean([r["mass_ratio"] for r in g])))
            ub.append(all(r["mass_ratio_is_upper_bound"] for r in g))
        line, = ax.plot(xs, ys, marker="o", label=f"reps={reps}")
        ubx = [x for x, u in zip(xs, ub) if u]
        uby = [y for y, u in zip(ys, ub) if u]
        ax.scatter(ubx, uby, marker="v", s=70, color=line.get_color(), zorder=3)
    ax.axhline(1.0, color="0.4", ls="--", lw=1)
    ax.text(Ts[0], 1.1, "parity with uniform sampling", color="0.4", fontsize=8, va="bottom")
    ax.set_yscale("log")
    ax.set_xticks(Ts)
    ax.set_xlabel("T (time slots)")
    ax.set_ylabel("QAOA optimal mass / uniform optimal mass")
    ax.set_title("QAOA concentration vs uniform sampling\n(▽ = upper bound: observed mass < 1/shots)")
    ax.legend()
    fig.tight_layout()
    return fig


def make_all_plots(rows, outdir=RESULTS_DIR):
    # NOTE: this writes the PLAIN experiment figures to docs/results/, including a
    # plain mass_ratio.png. The polished, web-facing mass-ratio figure is a
    # SEPARATE artifact at docs/figures/web/mass_ratio.png
    # (scripts/make_mass_ratio_figure.py) — different path, so a full sweep here
    # can never overwrite it.
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    figs = {
        "success_rate": plot_success_rate(rows),
        "optimal_mass": plot_optimal_mass(rows),
        "runtime_qubits": plot_runtime_qubits(rows),
    }
    if any("mass_ratio" in r for r in rows):
        figs["mass_ratio"] = plot_mass_ratio(rows)
    for name, fig in figs.items():
        fig.savefig(outdir / f"{name}.png", dpi=110, bbox_inches="tight")
    return figs


def main():
    import matplotlib
    matplotlib.use("Agg")
    print(f"running sweep (serial): T={T_VALUES} seeds={SEEDS} reps={REPS_VALUES} "
          f"(n_starts={N_STARTS}, shots={SHOTS}, maxiter={MAXITER})", flush=True)
    rows = run_and_stream()
    add_uniform_baseline(rows)                       # post-hoc uniform baseline
    write_csv(rows, CSV_PATH, fieldnames=AUG_FIELDNAMES)
    make_all_plots(rows, RESULTS_DIR)
    n_exact = sum(1 for r in rows if r["exact_match"])
    print(f"done: {len(rows)} runs, {n_exact} exact; CSV -> {CSV_PATH}", flush=True)


if __name__ == "__main__":
    main()
