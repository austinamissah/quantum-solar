"""Does the single-basin regime survive a second QAOA layer?

Pre-registered in ``docs/plans/basin-structure-reps2.md`` — read that first. Every
definition here (the instance, the basin cutoff, the reference rule, the clustering
rule, the seed budget, the α ladder, both falsification criteria) is fixed by that
document and nothing in this script may be re-chosen after seeing output.

Simulator and exact computation only. No QPU.

Reuses ``basin_study`` for the distance, the cutoff estimator and the clustering, so
the two studies cannot drift apart on what "distinct basin" means. What it does not
reuse is the *reference*: at reps=1 that came from recorded hardware angles, and no
reps=2 cp3 circuit has ever been run, so the plan pins a selection rule instead.

    python scripts/basin_study_reps2.py [--seeds 40] [--tag NAME]
    python scripts/basin_study_reps2.py --analyze-only
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore")

import basin_study as base  # noqa: E402
import experiment_hardware as hw  # noqa: E402
from quantum_solar import QAOASolver  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
PLAN = ROOT / "docs" / "plans" / "basin-structure-reps2.md"

# --- Fixed by the pre-registration -------------------------------------------
ALPHAS = base.ALPHAS             # the reps=1 ladder, unchanged, so rungs compare
INSTANCE = 1                     # the optimizer study's pre-designated primary
REPS = 2                         # the whole point of this study
HEADLINE_N = 40
REPORT_N = (5, 10, 20, 40)
ALPHA_STAR = 0.021
SHOTS, N_STARTS, MAXITER = 4096, 5, 200
TAU_RESAMPLES = base.TAU_RESAMPLES
ENCODING = "checkpoint3"
BAR = 5 / 2**6                   # 5 x uniform at m=6 = 0.078125, pre-registered


def require_registered() -> str:
    """Refuse to run unless the plan is committed. Registration cannot be back-dated.

    The project's discipline is that the criterion is fixed *before* the data, and the
    only durable evidence of that is the plan existing in history first. A plan that
    is still a working-tree file when the sweep runs is not a registration.
    """
    if not PLAN.exists():
        raise SystemExit(f"REFUSING TO RUN: {PLAN.relative_to(ROOT)} does not exist.")
    try:
        out = subprocess.run(
            ("git", "-C", str(ROOT), "log", "--format=%H", "-1", "--", str(PLAN)),
            capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SystemExit(f"REFUSING TO RUN: git unavailable, cannot verify the plan ({exc}).")
    if not out:
        raise SystemExit(
            "REFUSING TO RUN: the pre-registration is not committed. Commit "
            f"{PLAN.relative_to(ROOT)} first — a plan that is still uncommitted when "
            "the sweep runs is not a registration, and this study's whole claim to be "
            "a result rests on the criterion being fixed beforehand."
        )
    dirty = subprocess.run(
        ("git", "-C", str(ROOT), "status", "--porcelain", "--", str(PLAN)),
        capture_output=True, text=True).stdout.strip()
    if dirty:
        raise SystemExit(
            "REFUSING TO RUN: the pre-registration has uncommitted edits. Commit or "
            "revert them; a criterion that moves while the sweep runs is not pinned."
        )
    return out


def sweep(n_seeds, writer, handle):
    """Tune at every α over seeds 1..n_seeds on the designated instance."""
    out = {}
    for alpha in ALPHAS:
        problem, qubo, _ = hw.build_target(3, INSTANCE, REPS, encoding=ENCODING, alpha=alpha)
        opt_mask, feas_mask = hw.basis_masks(problem, qubo)
        X = hw.enumerate_bitstrings(qubo.num_vars).astype(float)
        energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset

        # Exactness: is the QUBO's own minimiser feasible? Read no mass without it.
        qubo_min = np.flatnonzero(np.isclose(energies, energies.min()))
        exact = bool(feas_mask[qubo_min].all() and opt_mask[qubo_min].any())

        dists, achieved, masses = [], [], []
        for seed in range(1, n_seeds + 1):
            result = QAOASolver(reps=REPS, n_starts=N_STARTS, shots=SHOTS,
                                seed=seed, maxiter=MAXITER).solve(problem, qubo)
            d = hw.exact_distribution(qubo, result.optimal_params, REPS)
            metrics = hw.scalar_metrics(d, opt_mask, feas_mask)
            h = float(d @ energies)
            dists.append(d)
            achieved.append(h)
            masses.append(metrics["optimal_mass"])
            writer.writerow({"instance_seed": INSTANCE, "alpha": alpha, "reps": REPS,
                             "tuning_seed": seed, "achieved_H": round(h, 8),
                             "ideal_opt_mass": round(metrics["optimal_mass"], 8),
                             "feasibility": round(metrics["feasibility"], 8),
                             "qubo_min_is_optimum": exact,
                             "params": json.dumps([float(p) for p in result.optimal_params])})
            handle.flush()
        out[alpha] = {"dists": np.array(dists), "achieved": np.array(achieved),
                      "masses": np.array(masses), "exact": exact}
        print(f"  alpha={alpha:<7} done  <H> {min(achieved):.4f}..{max(achieved):.4f}  "
              f"best mass {max(masses):.4f}  {'exact' if exact else 'INFEASIBLE min'}",
              flush=True)
    return out


def reference_and_tau(swept):
    """The α* reference by the pinned rule, and τ estimated from it.

    The rule is fixed in the plan: lowest achieved `<H>` at α* over the pinned seed
    budget. The value is computed here and reported, never chosen.
    """
    cell = swept[ALPHA_STAR]
    pick = int(np.argmin(cell["achieved"]))
    reference = cell["dists"][pick]
    rng = np.random.default_rng(0)
    draws = [base.tvd(reference, rng.multinomial(SHOTS, reference) / SHOTS)
             for _ in range(TAU_RESAMPLES)]
    return reference, pick, float(np.mean(draws)), float(np.std(draws))


def analyse(swept, reference, tau):
    """Everything the pre-registration asks to be reported, per α."""
    rows = []
    for alpha, cell in swept.items():
        dists, achieved, masses = cell["dists"], cell["achieved"], cell["masses"]
        row = {"alpha": alpha, "qubo_min_is_optimum": cell["exact"]}
        for label, thr in (("half", tau / 2), ("tau", tau), ("double", 2 * tau)):
            row[f"basins_complete_{label}"] = base.cluster_count(dists, thr, "complete")
        row["basins_single_tau"] = base.cluster_count(dists, tau, "single")
        row["linkage_disagrees"] = bool(row["basins_single_tau"] != row["basins_complete_tau"])
        row["basins_by_N"] = {str(n): base.cluster_count(dists[:n], tau, "complete")
                              for n in REPORT_N if n <= len(dists)}

        lowest_H = int(np.argmin(achieved))
        row["best_mass"] = float(masses.max())
        row["lowest_H_mass"] = float(masses[lowest_H])
        row["clears_bar"] = int((masses >= BAR).sum())
        row["tvd_max_pairwise"] = float(max(
            base.tvd(dists[i], dists[j])
            for i in range(len(dists)) for j in range(i + 1, len(dists))))
        row["tvd_to_reference"] = float(base.tvd(dists[lowest_H], reference))
        row["H_spread"] = float(achieved.max() - achieved.min())

        # Per-basin best mass, so "the best basin" is a defined object.
        labels = basin_labels(dists, tau)
        row["basin_best_mass"] = sorted(
            (float(masses[labels == b].max()) for b in np.unique(labels)), reverse=True)
        rows.append(row)
    return rows


def basin_labels(distributions, threshold):
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    n = len(distributions)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d[i, j] = d[j, i] = base.tvd(distributions[i], distributions[j])
    z = linkage(squareform(d, checks=False), method="complete")
    return fcluster(z, t=threshold, criterion="distance")


def verdicts(rows):
    """Both registered predictions, at the pinned definitions and nothing else."""
    star = next(r for r in rows if r["alpha"] == ALPHA_STAR)
    p1_basins = star["basins_complete_tau"]
    p2_best = star["best_mass"]
    return {
        "P1_single_basin_does_not_survive": {
            "prediction": "basin count at alpha* > 1",
            "measured_basins": p1_basins,
            "falsified": p1_basins == 1,
        },
        "P2_best_basin_falls_short": {
            "prediction": f"max ideal optimal mass at alpha* < {BAR}",
            "measured_best_mass": p2_best,
            "bar": BAR,
            "falsified": bool(p2_best >= BAR),
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=HEADLINE_N)
    parser.add_argument("--instance", type=int, default=INSTANCE,
                        help="default is the registered primary; other values are "
                             "robustness sweeps and cannot move the registered verdict")
    parser.add_argument("--tag", default="")
    parser.add_argument("--analyze-only", action="store_true")
    args = parser.parse_args()

    commit = require_registered()
    globals()["INSTANCE"] = args.instance
    suffix = f"_{args.tag}" if args.tag else ""
    csv_path = RESULTS / f"basin_study_reps2{suffix}.csv"
    json_path = RESULTS / f"basin_study_reps2{suffix}.json"
    npz_path = RESULTS / f"basin_distributions_reps2{suffix}.npz"

    print(f"Pre-registration committed at {commit[:12]} — proceeding.")
    print(f"instance {INSTANCE}, reps {REPS}, {len(ALPHAS)} alphas x {args.seeds} seeds")
    if INSTANCE != 1:
        print("NOTE: not the registered primary instance; this is a robustness sweep "
              "and cannot move the registered verdict.")

    if args.analyze_only:
        stored = np.load(npz_path)
        swept = {}
        for alpha in ALPHAS:
            key = f"a{alpha}"
            swept[alpha] = {"dists": stored[f"{key}_d"], "achieved": stored[f"{key}_h"],
                            "masses": stored[f"{key}_m"], "exact": bool(stored[f"{key}_e"])}
    else:
        fields = ["instance_seed", "alpha", "reps", "tuning_seed", "achieved_H",
                  "ideal_opt_mass", "feasibility", "qubo_min_is_optimum", "params"]
        with csv_path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            swept = sweep(args.seeds, writer, handle)
        np.savez_compressed(npz_path, **{
            f"a{a}_{k[0]}": v[k] for a, v in swept.items()
            for k in ("dists", "achieved", "masses")} | {
            f"a{a}_e": np.array(v["exact"]) for a, v in swept.items()})

    reference, pick, tau, tau_sd = reference_and_tau(swept)
    rows = analyse(swept, reference, tau)
    result = {
        "_source": "Generated by scripts/basin_study_reps2.py; pre-registered in "
                   "docs/plans/basin-structure-reps2.md. Simulator only, no QPU.",
        "plan_commit": commit,
        "instance_seed": INSTANCE, "reps": REPS, "encoding": ENCODING,
        "alphas": list(ALPHAS), "alpha_star": ALPHA_STAR,
        "headline_N": args.seeds, "report_N": list(REPORT_N),
        "bar": BAR,
        "tau": round(tau, 6), "tau_sd": round(tau_sd, 6),
        "tau_resamples": TAU_RESAMPLES,
        "reference_rule": "lowest achieved <H> at alpha*, over the pinned seed budget",
        "reference_tuning_seed": pick + 1,
        "solver": {"reps": REPS, "n_starts": N_STARTS, "shots": SHOTS, "maxiter": MAXITER},
        "by_alpha": rows,
        "verdicts": verdicts(rows),
    }
    json_path.write_text(json.dumps(result, indent=1) + "\n")

    print(f"\ntau = {tau:.6f} (sd {tau_sd:.6f}), reference = tuning seed {pick + 1}")
    print(f"{'alpha':<8}{'basins':>7}{'best mass':>11}{'lowest-H':>10}{'clears':>8}  exact")
    for row in rows:
        print(f"{row['alpha']:<8}{row['basins_complete_tau']:>7}"
              f"{row['best_mass']:>11.4f}{row['lowest_H_mass']:>10.4f}"
              f"{row['clears_bar']:>8}  {row['qubo_min_is_optimum']}")
    print()
    for name, v in result["verdicts"].items():
        print(f"{name}: {'FALSIFIED' if v['falsified'] else 'held'}  {v}")
    print(f"\nwrote {json_path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
