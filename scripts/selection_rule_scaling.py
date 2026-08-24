"""Does the selection rule survive a size you cannot enumerate?

Pre-registered in ``docs/plans/selection-rule-scaling.md`` — read that first. The
sizes, the seed budget, both predictions and their falsification criteria are fixed
there and nothing here may be re-chosen after seeing output.

Simulator and exact computation only. No QPU.

    python scripts/selection_rule_scaling.py [--seeds 20]
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

import experiment_hardware as hw  # noqa: E402
from quantum_solar import QAOASolver  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "docs" / "results"
PLAN = ROOT / "docs" / "plans" / "selection-rule-scaling.md"

# --- Fixed by the pre-registration -------------------------------------------
SLOTS = (4, 5, 6, 7)
INSTANCE = 1
REPS = 2
ALPHA_STAR = 0.021
HEADLINE_N = 20
SHOTS, N_STARTS, MAXITER = 4096, 5, 200
ENCODING = "checkpoint3"
SAMPLE_DRAWS = 200          # resamples used to measure identifiability


def require_registered() -> str:
    if not PLAN.exists():
        raise SystemExit(f"REFUSING TO RUN: {PLAN.relative_to(ROOT)} does not exist.")
    out = subprocess.run(
        ("git", "-C", str(ROOT), "log", "--format=%H", "-1", "--", str(PLAN)),
        capture_output=True, text=True).stdout.strip()
    if not out:
        raise SystemExit(
            "REFUSING TO RUN: the pre-registration is not committed. Fix that first — "
            "a criterion chosen after the data is not a criterion."
        )
    if subprocess.run(("git", "-C", str(ROOT), "status", "--porcelain", "--", str(PLAN)),
                      capture_output=True, text=True).stdout.strip():
        raise SystemExit("REFUSING TO RUN: the pre-registration has uncommitted edits.")
    return out


def identifiable(distribution, opt_index, feasible, energies, rng) -> float:
    """Fraction of shot samples in which the true optimum is recoverable.

    This is the direct rule's precondition, measured the way a practitioner would
    meet it: draw shots, keep the outcomes that decode to feasible schedules, take
    the cheapest, and ask whether it is the true optimum. If the optimum is never
    sampled, the cheapest feasible thing seen is something else and the rule has
    silently selected on the wrong state.
    """
    hits = 0
    for _ in range(SAMPLE_DRAWS):
        counts = rng.multinomial(SHOTS, distribution)
        seen = np.flatnonzero(counts > 0)
        seen_feasible = seen[feasible[seen]]
        if len(seen_feasible) and int(seen_feasible[np.argmin(energies[seen_feasible])]) == opt_index:
            hits += 1
    return hits / SAMPLE_DRAWS


def sweep(n_seeds, writer, handle):
    rng = np.random.default_rng(0)
    out = {}
    for slots in SLOTS:
        problem, qubo, _ = hw.build_target(slots, INSTANCE, REPS,
                                           encoding=ENCODING, alpha=ALPHA_STAR)
        m = qubo.num_vars
        opt_mask, feas_mask = hw.basis_masks(problem, qubo)
        X = hw.enumerate_bitstrings(m).astype(float)
        energies = np.einsum("bi,ij,bj->b", X, qubo.Q, X) + qubo.offset
        opt_index = int(np.flatnonzero(opt_mask)[0])
        cheapest_feasible = int(np.flatnonzero(feas_mask)[
            int(np.argmin(energies[feas_mask]))])

        rows = []
        for seed in range(1, n_seeds + 1):
            result = QAOASolver(reps=REPS, n_starts=N_STARTS, shots=SHOTS,
                                seed=seed, maxiter=MAXITER).solve(problem, qubo)
            p = hw.exact_distribution(qubo, result.optimal_params, REPS)
            q = np.clip(p, 1e-300, None)
            row = {
                "T": slots, "qubits": m, "tuning_seed": seed,
                "optimal_mass": float(p[opt_mask].sum()),
                "feasible_mass": float(p[feas_mask].sum()),
                "best_feasible_mass": float(p[cheapest_feasible]),
                "achieved_H": float(p @ energies),
                "entropy": float(-(q * np.log(q)).sum()),
                "participation": float(1 / np.square(p).sum()),
                "identifiable": identifiable(p, opt_index, feas_mask, energies, rng),
            }
            rows.append(row)
            writer.writerow(row)
            handle.flush()
        out[slots] = {"rows": rows, "qubits": m, "uniform": 1 / 2**m,
                      "bar": 5 / 2**m}
        best = max(r["optimal_mass"] for r in rows)
        print(f"  T={slots} m={m:<3} best mass {best:.6f}  bar {5/2**m:.6f}  "
              f"mean identifiable {np.mean([r['identifiable'] for r in rows]):.2f}",
              flush=True)
    return out


def analyze(swept):
    """Per size: what each rule picks, and whether the size is informative at all."""
    per_size = []
    for slots, cell in swept.items():
        rows = cell["rows"]
        masses = np.array([r["optimal_mass"] for r in rows])
        best = int(np.argmax(masses))

        picks = {}
        for name, key, sign in (("feasible_mass", "feasible_mass", 1),
                                ("lowest_H", "achieved_H", -1),
                                ("lowest_entropy", "entropy", -1),
                                ("lowest_participation", "participation", -1),
                                ("best_feasible_mass", "best_feasible_mass", 1)):
            values = np.array([sign * r[key] for r in rows])
            pick = int(np.argmax(values))
            rank = int(np.flatnonzero(np.argsort(-values) == best)[0]) + 1
            picks[name] = {"picked_seed": pick + 1,
                           "picked_mass": float(masses[pick]),
                           "rank_of_argmax": rank}

        per_size.append({
            "T": slots, "qubits": cell["qubits"],
            "uniform": cell["uniform"], "bar": cell["bar"],
            "best_mass": float(masses.max()),
            "mean_mass": float(masses.mean()),
            "any_above_uniform": bool((masses > cell["uniform"]).any()),
            "any_clears_scaled_bar": bool((masses >= cell["bar"]).any()),
            "mean_identifiable": float(np.mean([r["identifiable"] for r in rows])),
            "tunings_mostly_identifiable": int(
                sum(1 for r in rows if r["identifiable"] >= 0.5)),
            "n": len(rows),
            "rules": picks,
        })
    return per_size


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=HEADLINE_N)
    args = parser.parse_args()

    commit = require_registered()
    print(f"Pre-registration committed at {commit[:12]} — proceeding.")
    print(f"instance {INSTANCE}, reps {REPS}, alpha* {ALPHA_STAR}, "
          f"T in {SLOTS} x {args.seeds} seeds\n")

    fields = ["T", "qubits", "tuning_seed", "optimal_mass", "feasible_mass",
              "best_feasible_mass", "achieved_H", "entropy", "participation",
              "identifiable"]
    csv_path = RESULTS / "selection_rule_scaling.csv"
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        swept = sweep(args.seeds, writer, handle)

    per_size = analyze(swept)
    largest = max(per_size, key=lambda r: r["T"])

    wins = sum(1 for r in per_size
               if r["rules"]["feasible_mass"]["picked_mass"]
               > r["rules"]["lowest_H"]["picked_mass"])
    losses = sum(1 for r in per_size
                 if r["rules"]["feasible_mass"]["picked_mass"]
                 < r["rules"]["lowest_H"]["picked_mass"])

    result = {
        "_source": "Generated by scripts/selection_rule_scaling.py; pre-registered in "
                   "docs/plans/selection-rule-scaling.md. Simulator only, no QPU.",
        "plan_commit": commit,
        "instance": INSTANCE, "reps": REPS, "alpha_star": ALPHA_STAR,
        "slots": list(SLOTS), "headline_N": args.seeds,
        "solver": {"n_starts": N_STARTS, "shots": SHOTS, "maxiter": MAXITER},
        "by_size": per_size,
        "verdicts": {
            "P1_direct_rule_dies_with_size": {
                "prediction": "at the largest T, the optimum is recoverable from a "
                              "4096-shot sample in fewer than half the tunings",
                "largest_T": largest["T"],
                "tunings_mostly_identifiable": largest["tunings_mostly_identifiable"],
                "of": largest["n"],
                "falsified": largest["tunings_mostly_identifiable"] >= largest["n"] / 2,
            },
            "P2_feasible_mass_survives": {
                "prediction": "feasible mass picks a tuning at least as good as "
                              "lowest-<H> in more sizes than not",
                "wins": wins, "losses": losses, "sizes": len(per_size),
                "falsified": wins < losses,
            },
        },
        "informative": {
            "sizes_with_mass_above_uniform": [r["T"] for r in per_size
                                              if r["any_above_uniform"]],
            "note": "a size where no tuning beats uniform is a choice among noise; "
                    "the plan says in advance that such a size proves nothing",
        },
    }
    (RESULTS / "selection_rule_scaling.json").write_text(json.dumps(result, indent=1) + "\n")

    print(f"\n{'T':>3}{'m':>4}{'best mass':>11}{'uniform':>10}{'>unif?':>8}"
          f"{'ident.':>8}{'feas->':>10}{'<H>->':>10}{'rank(feas)':>11}")
    for r in per_size:
        R = r["rules"]
        print(f"{r['T']:>3}{r['qubits']:>4}{r['best_mass']:>11.6f}{r['uniform']:>10.6f}"
              f"{str(r['any_above_uniform']):>8}{r['mean_identifiable']:>8.2f}"
              f"{R['feasible_mass']['picked_mass']:>10.6f}"
              f"{R['lowest_H']['picked_mass']:>10.6f}"
              f"{R['feasible_mass']['rank_of_argmax']:>11}")
    print()
    for name, v in result["verdicts"].items():
        print(f"{name}: {'FALSIFIED' if v['falsified'] else 'held'}  {v}")


if __name__ == "__main__":
    main()
