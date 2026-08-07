"""Does α* buy reproducibility? Basin count vs penalty weight.

Pre-registered in ``docs/plans/basin-structure.md`` — read that first. Every
definition here (the basin cutoff, the clustering rule, the seed budget, the α
ladder, the falsification criteria) is fixed by that document and nothing in this
script may be re-chosen after seeing output.

Simulator and exact computation only. No QPU.

Streams scalars to CSV as it goes and saves the ideal distributions per instance,
so the analysis can be re-run without re-tuning (a full sweep is ~34 min per
instance).

    python scripts/basin_study.py [--instances 0,1,2] [--seeds 40] [--tag NAME]
    python scripts/basin_study.py --analyze-only
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

warnings.filterwarnings("ignore")

import experiment_hardware as hw  # noqa: E402
from quantum_solar import QAOASolver  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"

# --- Fixed by the pre-registration -------------------------------------------
ALPHAS = (0.003, 0.006, 0.010, 0.0209, 0.021, 0.030, 0.060, 0.100, 0.300, 1.000)
PRIMARY_INSTANCE = 0            # T=3, seed 0, checkpoint(3), reps=1 — the hardware instance
ROBUSTNESS_INSTANCES = (1, 2)   # reported, never decides the verdict
HEADLINE_N = 40
REPORT_N = (5, 10, 20, 40)
ALPHA_STAR = 0.021              # the weight every hardware run used
SHOTS, N_STARTS, MAXITER, REPS = 4096, 5, 200, 1
TAU_RESAMPLES = 400
ENCODING = "checkpoint3"


def tvd(p, q) -> float:
    return 0.5 * float(np.abs(np.asarray(p) - np.asarray(q)).sum())


def reference_distribution():
    """The α* anchor: cp3 @ α=0.021 with the angles the hardware runs recorded."""
    records = json.loads((RESULTS / "hardware_params_replication.json").read_text())
    record = next(r for r in records
                  if r.get("encoding") == "checkpoint3" and r.get("alpha") == ALPHA_STAR)
    _, qubo, _ = hw.build_target(3, 0, REPS, encoding=ENCODING, alpha=ALPHA_STAR)
    return hw.exact_distribution(qubo, record["params"], REPS)


def compute_tau(reference) -> float:
    """τ = E[TVD(ideal, multinomial sample)] at m=6, 4096 shots. Computed, not assumed.

    Two distributions closer than this are indistinguishable by the measurement this
    project performs, so a finer distinction has no operational meaning.
    """
    rng = np.random.default_rng(0)
    draws = [tvd(reference, rng.multinomial(SHOTS, reference) / SHOTS)
             for _ in range(TAU_RESAMPLES)]
    return float(np.mean(draws)), float(np.std(draws))


def cluster_count(distributions, threshold, method) -> int:
    """Basins among `distributions` at `threshold` under `method` linkage."""
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import squareform

    n = len(distributions)
    if n < 2:
        return n
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            d[i, j] = d[j, i] = tvd(distributions[i], distributions[j])
    z = linkage(squareform(d, checks=False), method=method)
    return int(fcluster(z, t=threshold, criterion="distance").max())


def sweep(instance_seed, n_seeds, writer, handle):
    """Tune at every α over seeds 1..n_seeds. Returns {alpha: (dists, energies)}."""
    out = {}
    for alpha in ALPHAS:
        problem, qubo, _ = hw.build_target(3, instance_seed, REPS,
                                           encoding=ENCODING, alpha=alpha)
        X = hw.enumerate_bitstrings(qubo.num_vars).astype(float)
        energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
        dists, achieved = [], []
        for seed in range(1, n_seeds + 1):
            result = QAOASolver(reps=REPS, n_starts=N_STARTS, shots=SHOTS,
                                seed=seed, maxiter=MAXITER).solve(problem, qubo)
            d = hw.exact_distribution(qubo, result.optimal_params, REPS)
            h = float(d @ energies)
            dists.append(d)
            achieved.append(h)
            writer.writerow({"instance_seed": instance_seed, "alpha": alpha,
                             "tuning_seed": seed, "achieved_H": round(h, 8),
                             "params": json.dumps([float(p) for p in result.optimal_params])})
            handle.flush()
        out[alpha] = (np.array(dists), np.array(achieved))
        print(f"  instance {instance_seed}  alpha={alpha:<7} done "
              f"(<H> {achieved and min(achieved):.4f}..{max(achieved):.4f})", flush=True)
    return out


def analyse(swept, reference, tau):
    """Everything the pre-registration asks to be reported, per α."""
    rows = []
    for alpha, (dists, achieved) in swept.items():
        row = {"alpha": alpha}
        for label, thr in (("half", tau / 2), ("tau", tau), ("double", 2 * tau)):
            row[f"basins_complete_{label}"] = cluster_count(dists, thr, "complete")
        row["basins_single_tau"] = cluster_count(dists, tau, "single")
        row["linkage_disagrees"] = bool(row["basins_single_tau"] != row["basins_complete_tau"])
        # Basin count and the lowest-<H> selection as functions of the seed budget.
        row["basins_by_N"] = {str(n): cluster_count(dists[:n], tau, "complete")
                              for n in REPORT_N if n <= len(dists)}
        sel = {}
        for n in REPORT_N:
            if n > len(dists):
                continue
            i = int(np.argmin(achieved[:n]))
            sel[str(n)] = {"seed": i + 1, "achieved_H": round(float(achieved[i]), 6),
                           "tvd_to_alpha_star_ref": round(tvd(dists[i], reference), 4)}
        row["lowest_H_selection_by_N"] = sel
        pair = [tvd(dists[i], dists[j]) for i in range(len(dists))
                for j in range(i + 1, len(dists))]
        row["tvd_spread"] = round(float(max(pair) - min(pair)), 4) if pair else 0.0
        row["tvd_max_pairwise"] = round(float(max(pair)), 4) if pair else 0.0
        row["H_spread"] = round(float(achieved.max() - achieved.min()), 6)
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--instances", default=None,
                    help="comma-separated instance seeds (default: primary + robustness)")
    ap.add_argument("--seeds", type=int, default=HEADLINE_N)
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    instances = ([int(s) for s in args.instances.split(",")] if args.instances
                 else [PRIMARY_INSTANCE, *ROBUSTNESS_INSTANCES])

    suffix = f"_{args.tag}" if args.tag else ""
    csv_path = RESULTS / f"basin_study{suffix}.csv"
    json_path = RESULTS / f"basin_study{suffix}.json"
    npz_path = RESULTS / f"basin_distributions{suffix}.npz"

    reference = reference_distribution()
    tau, tau_sd = compute_tau(reference)
    print(f"tau = {tau:.4f} (sd {tau_sd:.4f}) from {TAU_RESAMPLES} resamples "
          f"at {SHOTS} shots, m={int(np.log2(reference.size))}", flush=True)
    print(f"alpha ladder: {ALPHAS}")
    print(f"instances: {instances}   seeds 1..{args.seeds}   headline N={HEADLINE_N}\n", flush=True)

    import qiskit
    import qiskit_aer
    import scipy
    versions = {"qiskit": qiskit.__version__, "qiskit-aer": qiskit_aer.__version__,
                "scipy": scipy.__version__, "numpy": np.__version__}

    fields = ["instance_seed", "alpha", "tuning_seed", "achieved_H", "params"]
    store, report = {}, {}
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for instance in instances:
            swept = sweep(instance, args.seeds, writer, handle)
            report[str(instance)] = analyse(swept, reference, tau)
            for alpha, (dists, _) in swept.items():
                store[f"i{instance}_a{alpha}"] = dists
            np.savez_compressed(npz_path, **store)

    json_path.write_text(json.dumps({
        "_source": "Generated by scripts/basin_study.py; pre-registered in "
                   "docs/plans/basin-structure.md. Simulator/exact only, no QPU.",
        "tau": round(tau, 6), "tau_sd": round(tau_sd, 6), "tau_resamples": TAU_RESAMPLES,
        "alphas": list(ALPHAS), "alpha_star": ALPHA_STAR,
        "headline_N": HEADLINE_N, "report_N": list(REPORT_N),
        "primary_instance": PRIMARY_INSTANCE,
        "robustness_instances": list(ROBUSTNESS_INSTANCES),
        "solver": {"reps": REPS, "n_starts": N_STARTS, "shots": SHOTS, "maxiter": MAXITER},
        "versions": versions,
        "by_instance": report,
    }, indent=1) + "\n")
    print(f"\nwrote {csv_path.name}, {json_path.name}, {npz_path.name}")


if __name__ == "__main__":
    main()
